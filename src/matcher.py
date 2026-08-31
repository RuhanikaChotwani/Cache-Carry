"""
Offline Face Matching Module using Cosine Similarity against a local enrolled gallery.

Matches 512-d ArcFace embeddings against local watch-lists and personnel databases.
"""

from collections import defaultdict
from pathlib import Path
import pickle
import sys
from typing import Dict, List, Optional, Tuple
import numpy as np

# Compatibility bridge for galleries serialized under NumPy 2.x loaded under NumPy 1.x
if "numpy._core" not in sys.modules:
    try:
        import numpy.core as _core
        import numpy.core.numeric as _numeric
        import numpy.core.multiarray as _multiarray
        sys.modules["numpy._core"] = _core
        sys.modules["numpy._core.numeric"] = _numeric
        sys.modules["numpy._core.multiarray"] = _multiarray
    except Exception:
        pass


class SafeUnpickler(pickle.Unpickler):
    """Handles cross-version unpickling between NumPy 1.x and 2.x."""

    def find_class(self, module: str, name: str):
        if module.startswith("numpy._core"):
            module = module.replace("numpy._core", "numpy.core")
        return super().find_class(module, name)


class FaceMatcher:
    """
    Offline nearest-neighbor and centroid face matcher using normalized cosine similarity.
    """

    def __init__(
        self,
        gallery_path: str | Path,
        similarity_threshold: float = 0.45,
        unknown_label: str = "Unknown",
    ):
        self.gallery_path = Path(gallery_path)
        self.similarity_threshold = float(similarity_threshold)
        self.unknown_label = unknown_label

        # In-memory index
        self.names: List[str] = []
        self.embeddings: Optional[np.ndarray] = None  # (M, 512)
        self.labels: List[str] = []  # Length M
        self.centroids: Dict[str, np.ndarray] = {}  # {name: (512,)}

        if self.gallery_path.exists():
            self.load_gallery(self.gallery_path)
        else:
            print(
                f"[Matcher] Notice: Gallery file not found at {self.gallery_path}. "
                f"Operating in Unknown-only mode until enrollment is executed."
            )

    @property
    def is_empty(self) -> bool:
        return self.embeddings is None or len(self.embeddings) == 0

    def load_gallery(self, path: Path | str) -> None:
        """Loads serialized gallery from disk."""
        path = Path(path)
        with open(path, "rb") as f:
            data = SafeUnpickler(f).load()

        self.names = list(data.get("names", []))
        raw_embs = data.get("embeddings", [])
        self.embeddings = np.asarray(raw_embs, dtype=np.float32) if len(raw_embs) > 0 else None
        self.labels = list(data.get("labels", []))
        raw_centroids = data.get("centroids", {})
        self.centroids = {
            k: np.asarray(v, dtype=np.float32) for k, v in raw_centroids.items()
        }

        count = len(self.labels) if self.labels else 0
        print(
            f"[Matcher] Loaded gallery with {len(self.names)} identities "
            f"and {count} total face vectors from: {path}"
        )

    def save_gallery(self, path: Optional[Path | str] = None) -> None:
        """Saves current in-memory gallery to disk in a version-agnostic format."""
        target_path = Path(path) if path else self.gallery_path
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert numpy arrays to lists to avoid NumPy 1.x / 2.x pickle incompatibilities
        embs_list = self.embeddings.tolist() if self.embeddings is not None else []
        centroids_dict = {k: v.tolist() for k, v in self.centroids.items()}

        data = {
            "names": self.names,
            "embeddings": embs_list,
            "labels": self.labels,
            "centroids": centroids_dict,
        }
        with open(target_path, "wb") as f:
            pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)

        print(f"[Matcher] Saved gallery index to: {target_path}")

    def build_from_dict(self, enrollment_dict: Dict[str, List[np.ndarray]]) -> None:
        """
        Builds the gallery from a dictionary of {person_name: [list_of_512d_embeddings]}.
        Computes both individual instance embeddings and centroid representations.
        """
        all_embeddings = []
        all_labels = []
        names = []
        centroids = {}

        for name, emb_list in enrollment_dict.items():
            if not emb_list:
                continue

            names.append(name)
            embs_arr = np.asarray(emb_list, dtype=np.float32)  # (K, 512)

            # Ensure normalized
            norms = np.linalg.norm(embs_arr, axis=1, keepdims=True)
            norms = np.maximum(norms, 1e-12)
            embs_arr = embs_arr / norms

            for emb in embs_arr:
                all_embeddings.append(emb)
                all_labels.append(name)

            # Compute L2-normalized centroid (mean embedding)
            centroid = np.mean(embs_arr, axis=0)
            c_norm = np.linalg.norm(centroid)
            if c_norm > 1e-12:
                centroid = centroid / c_norm
            centroids[name] = centroid

        if all_embeddings:
            self.names = sorted(names)
            self.embeddings = np.vstack(all_embeddings)
            self.labels = all_labels
            self.centroids = centroids
        else:
            self.names = []
            self.embeddings = None
            self.labels = []
            self.centroids = {}

    def match(
        self, query_embedding: np.ndarray
    ) -> Tuple[str, float]:
        """
        Matches a single 512-d query embedding against the gallery.

        Returns:
            (identity_name, similarity_score)
            If max similarity < similarity_threshold, identity_name will be self.unknown_label.
        """
        if self.is_empty:
            return self.unknown_label, 0.0

        # Ensure query is normalized
        q = np.asarray(query_embedding, dtype=np.float32).flatten()
        q_norm = np.linalg.norm(q)
        if q_norm > 1e-12:
            q = q / q_norm

        # Matrix dot product: (1, 512) @ (512, M) -> (M,) cosine similarities
        similarities = np.dot(self.embeddings, q)

        # Aggregate max similarity per identity
        best_idx = int(np.argmax(similarities))
        max_sim = float(similarities[best_idx])
        predicted_name = self.labels[best_idx]

        if max_sim >= self.similarity_threshold:
            return predicted_name, max_sim
        else:
            return self.unknown_label, max_sim

    def match_batch(
        self, query_embeddings: np.ndarray
    ) -> List[Tuple[str, float]]:
        """
        Batch matching for multiple face vectors.
        query_embeddings shape: (B, 512)
        """
        if self.is_empty or len(query_embeddings) == 0:
            return [(self.unknown_label, 0.0) for _ in range(len(query_embeddings))]

        # Ensure queries normalized
        norms = np.linalg.norm(query_embeddings, axis=1, keepdims=True)
        norms = np.maximum(norms, 1e-12)
        qs = query_embeddings / norms

        # (B, 512) @ (512, M) -> (B, M)
        sim_matrix = np.dot(qs, self.embeddings.T)

        results = []
        for row in sim_matrix:
            best_idx = int(np.argmax(row))
            score = float(row[best_idx])
            name = self.labels[best_idx]
            if score >= self.similarity_threshold:
                results.append((name, score))
            else:
                results.append((self.unknown_label, score))
        return results

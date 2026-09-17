"""
Hugging Face Dataset Downloader.
Programmatically downloads and loads the Indian Pharmaceutical dataset
'revooda/indian-pharma-data' using the Hugging Face datasets library.

Saves raw snapshot to backend/data/raw/medicines_raw.csv.
"""

from pathlib import Path
import sys
from typing import Any

from datasets import DatasetDict, load_dataset
from backend.app import config

DATASET_NAME = "revooda/indian-pharma-data"
DEFAULT_RAW_OUTPUT = config.DATA_RAW_DIR / "medicines_raw.csv"


def download_dataset(
    dataset_name: str = DATASET_NAME,
    output_csv: Path | str | None = None,
    export_sample_size: int | None = 20000,
) -> Any:
    """
    Downloads/loads the Hugging Face dataset.
    Optionally exports a raw snapshot to CSV for inspection and offline use.
    """
    print(f"[Dataset] Loading '{dataset_name}' via Hugging Face datasets library...")
    dataset = load_dataset(dataset_name)

    split = "train"
    data_split = dataset[split] if isinstance(dataset, DatasetDict) else dataset
    total_rows = len(data_split)
    print(f"[Dataset] Successfully loaded {total_rows:,} records from '{dataset_name}'.")
    print(f"[Dataset] Features available: {data_split.column_names}")

    # Export raw snapshot to CSV if requested
    out_path = Path(output_csv) if output_csv else DEFAULT_RAW_OUTPUT
    out_path.parent.mkdir(parents=True, exist_ok=True)

    sample_size = min(export_sample_size, total_rows) if export_sample_size else total_rows
    print(f"[Dataset] Exporting {sample_size:,} raw rows to {out_path}...")

    df = data_split.select(range(sample_size)).to_pandas()
    df.to_csv(out_path, index=False)
    print(f"[Dataset] Raw export complete: {out_path} ({out_path.stat().st_size / (1024 * 1024):.2f} MB)")

    return data_split


if __name__ == "__main__":
    download_dataset()

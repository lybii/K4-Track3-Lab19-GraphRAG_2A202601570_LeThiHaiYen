"""Execute the lab notebook and persist outputs after every cell."""

from pathlib import Path

import nbformat
from nbclient import NotebookClient


NOTEBOOK = Path("Day19_GraphRAG_vs_FlatRAG_Production_Lab_Guide.ipynb")


def main():
    notebook = nbformat.read(NOTEBOOK, as_version=4)
    client = NotebookClient(
        notebook,
        timeout=3600,
        kernel_name="python3",
        resources={"metadata": {"path": str(Path.cwd())}},
    )

    with client.setup_kernel():
        for index, cell in enumerate(notebook.cells):
            if cell.cell_type != "code":
                continue
            title = next(
                (line.strip() for line in cell.source.splitlines() if line.strip()),
                "empty cell",
            )
            print(f"[{index + 1}/{len(notebook.cells)}] {title}", flush=True)
            cell.outputs = []
            cell.execution_count = None
            try:
                client.execute_cell(cell, index)
            finally:
                nbformat.write(notebook, NOTEBOOK)

    print("Notebook execution completed.", flush=True)


if __name__ == "__main__":
    main()

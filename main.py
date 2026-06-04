"""
DocumentCloud Textract Table Analysis Add-On.

Uses Amazon Textract AnalyzeDocument (TABLES) to extract and format tables as markdown.
Stores structured text back in DocumentCloud at the page level.
"""

import os

import boto3
from textractor import Textractor
from textractor.data.constants import TextractFeatures

from documentcloud.addon import AddOn


def table_to_markdown(table) -> str:
    rows = []
    for row in table.rows:
        cells = [cell.text.strip().replace("|", "\\|") for cell in row.cells]
        rows.append("| " + " | ".join(cells) + " |")
    if rows:
        col_count = len(list(table.rows)[0].cells)
        separator = "| " + " | ".join(["---"] * col_count) + " |"
        rows.insert(1, separator)
    return "\n".join(rows)


class TextractTableAnalysis(AddOn):
    """Extracts tables from documents using AWS Textract AnalyzeDocument (TABLES)."""

    def main(self):
        to_tag = self.data.get("to_tag", False)

        extractor = Textractor(
            region_name=os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
        )

        for document in self.get_documents():
            self.set_message(f"Processing: {document.title}")

            try:
                s3_uri = f"s3://s3.documentcloud.org/documents/{document.id}/{document.slug}.pdf"

                document_info = extractor.start_document_analysis(
                    s3_uri,
                    features=[TextractFeatures.TABLES],
                    save_image=False,
                )

                pages = []
                for page in document_info.pages:
                    table_md = "\n\n".join(
                        table_to_markdown(t) for t in page.tables if t.rows
                    )
                    page_text = page.text + ("\n\n" + table_md if table_md else "")

                    pages.append({
                        "page_number": page.page_num - 1,
                        "text": page_text,
                        "ocr": "textract-tables",
                        "positions": [],
                    })

                self.client.patch(
                    f"documents/{document.id}/",
                    json={"pages": pages},
                )

                if to_tag:
                    document.data["ocr_engine"] = ["textract-tables"]
                    document.save()

                self.set_message(f"Done: {document.title} ({len(pages)} pages)")

            except Exception as exc:
                self.set_message(f"Error processing {document.title}: {exc}")
                raise

        self.set_message("Textract Table Analysis complete.")


if __name__ == "__main__":
    TextractTableAnalysis().main()

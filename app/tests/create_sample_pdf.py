"""Script to generate a sample PDF for integration testing."""

from pathlib import Path

from reportlab.lib.pagesizes import letter  # type: ignore
from reportlab.pdfgen import canvas  # type: ignore


def create_sample_pdf(output_path: Path) -> None:
    """Create a simple sample PDF file with text.

    Args:
        output_path: Path where the PDF will be saved
    """
    # Create the parent directory if it doesn't exist
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Create a PDF with reportlab
    c = canvas.Canvas(str(output_path), pagesize=letter)

    # Add content to multiple pages
    for page in range(1, 4):  # Create 3 pages
        c.setFont("Helvetica", 12)
        c.drawString(100, 750, f"Test PDF Document - Page {page}")
        c.drawString(100, 730, "Created for OCR testing")
        c.drawString(100, 710, f"This is sample text on page {page}")
        c.drawString(
            100, 690, "This text should be extracted by direct text extraction."
        )
        c.drawString(
            100, 670, "Lorem ipsum dolor sit amet, consectetur adipiscing elit."
        )
        c.drawString(
            100,
            650,
            "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.",
        )

        # Add page number at the bottom
        c.setFont("Helvetica", 8)
        c.drawString(280, 50, f"Page {page} of 3")

        if page < 3:  # Don't add a new page after the last page
            c.showPage()

    # Save the PDF
    c.save()
    print(f"Sample PDF created at: {output_path}")


if __name__ == "__main__":
    # Path to save the sample PDF
    test_data_dir = Path(__file__).parent / "test_integration" / "test_data"
    sample_pdf_path = test_data_dir / "sample.pdf"

    create_sample_pdf(sample_pdf_path)

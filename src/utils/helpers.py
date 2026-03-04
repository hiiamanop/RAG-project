from fpdf import FPDF
import re

def create_pdf(text: str) -> bytes:
    """
    Generate PDF from text content.
    Returns bytes object.
    """
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Clean markdown (basic)
    # Remove bold/italic markers for cleaner PDF text
    clean_text = text.replace("**", "").replace("*", "").replace("`", "")
    
    # Handle encoding
    clean_text = clean_text.encode('latin-1', 'replace').decode('latin-1')
    
    pdf.multi_cell(0, 10, txt=clean_text)
    
    # fpdf2 output(dest='S') returns a bytearray in newer versions
    output = pdf.output(dest='S')
    if isinstance(output, bytearray):
        return bytes(output)
    return output.encode('latin-1')

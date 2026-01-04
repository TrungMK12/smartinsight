import docx2txt
import re
import PyPDF2

def extract_text_from_pdf(path: str) -> str:
    reader = PyPDF2.PdfReader(path)
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text

def extract_text_from_docx(path: str) -> str:
    return docx2txt.process(path)

def extract_text_from_txt(path: str) -> str:
    with open(path,'r',encoding='utf-8') as f:
        return f.read()
    
def clean_text(text: str) -> str:
    text = re.sub(r'\n{2,}','\n',text)
    text = re.sub(r'Page\s*\d+\W*\s*\d+','',text,flags=re.IGNORECASE)
    text = re.sub(r'\s{2,}',' ',text)
    return text
    

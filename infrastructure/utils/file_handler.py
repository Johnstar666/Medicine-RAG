import os
import hashlib
from infrastructure.utils.logger_handler import logger
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader,TextLoader,Docx2txtLoader

def extract_text_from_docx_direct(filepath):
    """
    直接从DOCX文件中提取文本（不依赖外部库）
    DOCX文件本质上是ZIP压缩的XML文件
    """
    try:
        import zipfile
        import xml.etree.ElementTree as ET
        
        with zipfile.ZipFile(filepath, 'r') as zip_file:
            if 'word/document.xml' in zip_file.namelist():
                with zip_file.open('word/document.xml') as xml_file:
                    tree = ET.parse(xml_file)
                    root = tree.getroot()
                    text_parts = []
                    for elem in root.iter():
                        if elem.text and elem.text.strip():
                            text_parts.append(elem.text.strip())
                    return '\n'.join(text_parts)
        return None
    except Exception as e:
        logger.warning(f"[extract_text_from_docx_direct]提取失败: {e}")
        return None

def get_file_md5_hex(filepath:str):
    if not os.path.exists(filepath):
        logger.error(f"[md5计算]文件{filepath}不存在")
    if not os.path.isfile(filepath):
        logger.error(f"[md5计算]路径{filepath}不是文件")
    md5_obj = hashlib.md5()
    chunk_size=4096
    try:
        with open(filepath, "rb") as f:
            while chunk := f.read(chunk_size):
                md5_obj.update(chunk)
            md5_hex = md5_obj.hexdigest()
            return md5_hex
    except Exception as e:
        logger.error(f"计算文件{filepath}失败：{str(e)}")

def listdir_with_allowed_types(path:str,allowed_types:tuple[str]):
    files=[]
    if not os.path.isdir(path):
        logger.error(f"[listdir_with_allowed_type]{path}不是文件夹")
        return allowed_types
    for f in os.listdir(path):
        if f.endswith(allowed_types):
            files.append(os.path.join(path,f))
    return tuple(files)

def pdf_loader(filepath:str,password=None)->list[Document]:
    docs = PyPDFLoader(filepath,password).load()
    for doc in docs:
        doc.metadata["source"] = os.path.basename(filepath)
    return docs

def text_loader(filepath:str,)->list[Document]:
    docs = TextLoader(filepath,encoding='utf-8').load()
    for doc in docs:
        doc.metadata["source"] = os.path.basename(filepath)
    return docs

def doc_loader(filepath:str)->list[Document]:
    docs = []
    # 使用LibreOffice（绝对路径）
    try:
        import subprocess
        libreoffice_path = r"C:\Program Files\LibreOffice\program\soffice.exe"
        output_dir = os.path.dirname(filepath)
        result = subprocess.run([libreoffice_path, '--convert-to', 'txt', '--outdir', output_dir, filepath],
                              capture_output=True, 
                              timeout=60)
        txt_file = os.path.splitext(filepath)[0] + '.txt'
        if os.path.exists(txt_file):
            with open(txt_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            os.remove(txt_file)
            if content.strip():
                doc = Document(page_content=content)
                doc.metadata["source"] = os.path.basename(filepath)
                docs.append(doc)
    except Exception as e:
        logger.warning(f"[doc_loader]无法使用LibreOffice加载DOC文件{filepath}: {str(e)}")
    
    # 回退到docx2txt
    try:
        docs = Docx2txtLoader(filepath).load()
        for doc in docs:
            doc.metadata["source"] = os.path.basename(filepath)
        return docs
    except Exception as e2:
        logger.warning(f"[doc_loader]无法加载DOC文件{filepath}: {str(e2)}")
        return docs

def docx_loader(filepath:str)->list[Document]:
    docs = []
    # 首先尝试直接解析ZIP
    try:
        content = extract_text_from_docx_direct(filepath)
        if content:
            doc = Document(page_content=content)
            doc.metadata["source"] = os.path.basename(filepath)
            docs.append(doc)
            return docs
    except Exception as e:
        logger.warning(f"[docx_loader]直接解析失败: {e}")
    
    try:
        docs = Docx2txtLoader(filepath).load()
        for doc in docs:
            doc.metadata["source"] = os.path.basename(filepath)
        return docs
    except Exception as e1:
        try:
            import win32com.client as win32
            word = win32.gencache.EnsureDispatch('Word.Application')
            doc = word.Documents.Open(filepath)
            content = doc.Content.Text
            doc.Close()
            word.Quit()
            doc_obj = Document(page_content=content)
            doc_obj.metadata["source"] = os.path.basename(filepath)
            docs.append(doc_obj)
            return docs
        except Exception as e2:
            logger.warning(f"[docx_loader]无法加载DOCX文件{filepath}: {str(e1)}")
            # 尝试使用LibreOffice（绝对路径）
            try:
                import subprocess
                libreoffice_path = r"C:\Program Files\LibreOffice\program\soffice.exe"
                output_dir = os.path.dirname(filepath)
                result = subprocess.run([libreoffice_path, '--convert-to', 'txt', '--outdir', output_dir, filepath],
                                      capture_output=True, 
                                      timeout=60)
                txt_file = os.path.splitext(filepath)[0] + '.txt'
                if os.path.exists(txt_file):
                    with open(txt_file, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    os.remove(txt_file)
                    if content.strip():
                        doc = Document(page_content=content)
                        doc.metadata["source"] = os.path.basename(filepath)
                        docs.append(doc)
            except Exception as e3:
                logger.warning(f"[docx_loader]无法使用LibreOffice加载DOCX文件{filepath}: {str(e3)}")
            return docs

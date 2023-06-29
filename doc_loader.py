import pypandoc
import os
import fitz
from paddleocr import PaddleOCR
import torch


def docx_to_txt(filepath, dir_path="tmp_files"):
    full_dir_path = os.path.join(os.path.dirname(filepath), dir_path)
    if not os.path.exists(full_dir_path):
        os.makedirs(full_dir_path)
    txt_file_path = os.path.join(full_dir_path, f"{os.path.split(filepath)[-1]}.txt")
    pypandoc.convert_file(filepath, 'plain', outputfile=txt_file_path)
    return txt_file_path


def image_to_txt(filepath, dir_path="tmp_files", show_log=False):
    full_dir_path = os.path.join(os.path.dirname(filepath), dir_path)
    if not os.path.exists(full_dir_path):
        os.makedirs(full_dir_path)
    filename = os.path.split(filepath)[-1]
    ocr = PaddleOCR(use_angle_cls=True, lang="ch", 
                    use_gpu=torch.cuda.is_available(), show_log=show_log)
    result = ocr.ocr(img=filepath)

    ocr_result = [i[1][0] for line in result for i in line]
    txt_file_path = os.path.join(full_dir_path, "%s.txt" % (filename))
    with open(txt_file_path, 'w', encoding='utf-8') as fout:
        fout.write("\n".join(ocr_result))
    return txt_file_path


def pdf_to_txt(filepath, dir_path="tmp_files", show_log=False,
               image_ocr=True):
    full_dir_path = os.path.join(os.path.dirname(filepath), dir_path)
    if not os.path.exists(full_dir_path):
        os.makedirs(full_dir_path)
    ocr = PaddleOCR(use_angle_cls=True, lang="ch", 
                    use_gpu=torch.cuda.is_available(), show_log=show_log)
    doc = fitz.open(filepath)
    txt_file_path = os.path.join(full_dir_path, f"{os.path.split(filepath)[-1]}.txt")
    img_name = os.path.join(full_dir_path, 'tmp.png')
    with open(txt_file_path, 'w', encoding='utf-8') as fout:
        for i in range(doc.page_count):
            page = doc[i]
            text = page.get_text("")
            fout.write(text)
            fout.write("\n")
            
            if image_ocr:
                img_list = page.get_images()
                for img in img_list:
                    pix = fitz.Pixmap(doc, img[0])
                    if pix.n - pix.alpha >= 4:
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                    pix.save(img_name)

                    result = ocr.ocr(img_name)
                    ocr_result = [i[1][0] for line in result for i in line]
                    fout.write("\n".join(ocr_result))
    if os.path.exists(img_name):
        os.remove(img_name)
    return txt_file_path

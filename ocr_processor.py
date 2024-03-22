import os
from PIL import Image
import pytesseract

class OCRProcessor:
    def __init__(self, input_path, output_path):
        self.input_path = input_path
        self.output_path = output_path
        if not os.path.exists(output_path):
            os.makedirs(output_path)

    def process_documents(self):
        for filename in os.listdir(self.input_path):
            if filename.endswith('.jpg'):  # Assuming images are already converted and saved as .jpg
                self.extract_text_from_image(filename)

    def extract_text_from_image(self, filename):
        image_path = os.path.join(self.input_path, filename)
        text = pytesseract.image_to_string(Image.open(image_path))
        output_base = os.path.splitext(filename)[0]
        text_file_path = os.path.join(self.output_path, f'{output_base}.txt')
        with open(text_file_path, 'w') as text_file:
            text_file.write(text)
        print(f'Extracted text from {filename} and saved to {text_file_path}')

if __name__ == '__main__':
    ocr_processor = OCRProcessor('converted_documents', 'ocr_texts')
    ocr_processor.process_documents()

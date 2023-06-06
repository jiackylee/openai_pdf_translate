import os
import sys
import asyncio
import httpx
from io import BytesIO
from itertools import cycle
from functools import partial
import PyPDF2
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTImage, LTText
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# 可以根据实际需求增加其他OpenAI API密钥，并根据需要进行替换
OPENAI_API_KEYS = ['your-api-key1', 'your-api-key2']

pdfmetrics.registerFont(TTFont('Vera', 'Vera.ttf'))  # 注册您期望的字体应用于生成的PDF文件中，请确保'.ttf'字体文件路径正确

class PDFTranslator:

    def __init__(self, pdf_path, target_language='zh-CN', max_token_length=4000):
        self.pdf_path = pdf_path
        self.target_language = target_language
        self.max_token_length = max_token_length
        self.client_pool = cycle(httpx.AsyncClient() for _ in range(len(OPENAI_API_KEYS)))

    async def aio_translate_text_openai(self, client, text, api_key):
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
        url = f"https://api.openai.com/v1/engines/text-davinci-003/completions"
        data = {
            "prompt": f"Translate the following English text to {self.target_language}:\n\n{text}",
            "max_tokens": self.max_token_length,
            "n": 1,
            "stop": None,
            "temperature": 0.8
        }
        try:
            response = await client.post(url, json=data, headers=headers)
            response.raise_for_status()
            translated_text = response.json()['choices'][0]['text'].strip()
            return translated_text
        except Exception as e:
            print(f"Error while translating text: {e}")
            return None

    async def do_translation(self, client, translations, texts, start, step, api_key):
        for i in range(start, len(texts), step):
            if isinstance(texts[i], LTImage):
                translations[i] = texts[i]
            else:
                translated_text = await self.aio_translate_text_openai(client, texts[i].get_text(), api_key)
                translations[i] = translated_text

    async def translate_and_write_to_pdf(self, output_pdf_path):
        pages = extract_pages(self.pdf_path)

        with BytesIO() as buffer:
            c = Canvas(buffer, pagesize=letter)
            c.setFont("Vera", 12)  # 使用前面注册过的Vera字体
            for pg_num, page in enumerate(pages):
                texts = []

                for element in page:
                    if isinstance(element, LTText):
                        texts.append(element)

                translations = [None] * len(texts)
                translation_tasks = []

                for i, (client, api_key) in enumerate(zip(self.client_pool, OPENAI_API_KEYS)):
                    task = asyncio.create_task(
                        self.do_translation(client, translations, texts, i, len(self.client_pool), api_key))
                    translation_tasks.append(task)

                await asyncio.gather(*translation_tasks)

                for text, translated_text in zip(texts, translations):
                    original_x, original_y = text.bbox[0], text.bbox[1]
                    c.drawString(original_x, original_y, text.get_text())
                    c.drawString(original_x, original_y - 14, translated_text)

                c.showPage()

            c.save()

            with open(output_pdf_path, 'wb') as f:
                f.write(buffer.getvalue())

    async def close_clients(self):
        # 关闭client连接
        for client in self.client_pool:
            await client.aclose()


async def main(input_path, output_path, target_language):
    pdf_translator = PDFTranslator(input_path, target_language=target_language)
    await pdf_translator.translate_and_write_to_pdf(output_path)
    await pdf_translator.close_clients()


if __name__ == '__main__':
    if len(sys.argv) < 3:
        print("Usage: python pdf_translator.py input_file output_file [target_language]")
        exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]
    target_language = sys.argv[3] if len(sys.argv) >= 4 else 'zh-CN'

    asyncio.run(main(input_file, output_file, target_language))
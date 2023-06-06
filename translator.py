import os
import sys
import asyncio
import httpx
from io import BytesIO
from itertools import cycle
from functools import partial
import PyPDF2
from pdfminer.high_level import extract_text
from reportlab.pdfgen.canvas import Canvas
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import tkinter as tk
from tkinter import filedialog, messagebox

OPENAI_API_KEYS = ['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', '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']

pdfmetrics.registerFont(TTFont('Vera', 'Vera.ttf'))  # 请确保'.ttf'字体文件路径正确

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
            translated_text = await self.aio_translate_text_openai(client, texts[i], api_key)
            translations[i] = translated_text

    async def translate_and_write_to_pdf(self, output_pdf_path):
        pdf_reader = PyPDF2.PdfReader(self.pdf_path)

        with BytesIO() as buffer:
            c = Canvas(buffer, pagesize=letter)
            c.setFont("Vera", 12)  # 使用前面注册过的Vera字体

            pdf_reader = PyPDF2.PdfReader(self.pdf_path)
            for pg_num in range(len(pdf_reader.pages)):
                page_text = extract_text(self.pdf_path, page_numbers=[pg_num]).strip()
                if not page_text:
                    continue

                translations = [None] * len(page_text.splitlines())
                translation_tasks = []

                client_pool_list = list(self.client_pool)
                api_keys_list = list(OPENAI_API_KEYS)
                for i, (client, api_key) in enumerate(zip(client_pool_list, api_keys_list)):
                    task = asyncio.create_task(
                        self.do_translation(client, translations, page_text.splitlines(), i, len(client_pool_list), api_key))
                    translation_tasks.append(task)

                await asyncio.gather(*translation_tasks)

                for i, (text, translated_text) in enumerate(zip(page_text.splitlines(), translations)):
                    c.drawString(30, 750 - i * 14, text)
                    c.drawString(30, 750 - i * 14 - 14, translated_text)

                c.showPage()

            c.save()

            with open(output_pdf_path, 'wb') as f:
                f.write(buffer.getvalue())

    async def close_clients(self):
        # 关闭client连接
        for client in self.client_pool:
            await client.aclose()


class TranslatorGUI(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("PDF Translator")
        self.geometry("300x200")

        input_label = tk.Label(self, text="Input PDF file:")
        input_label.grid(row=0, column=0, padx=10, pady=10, sticky=tk.W)

        self.input_var = tk.StringVar()
        input_entry = tk.Entry(self, textvariable=self.input_var, state='readonly')
        input_entry.grid(row=1, column=0, columnspan=2, sticky=tk.EW)

        input_button = tk.Button(self, text="Browse", command=self.select_input_file)
        input_button.grid(row=1, column=2, padx=10)

        output_label = tk.Label(self, text="Output PDF file:")
        output_label.grid(row=2, column=0, padx=10, pady=10, sticky=tk.W)

        self.output_var = tk.StringVar()
        output_entry = tk.Entry(self, textvariable=self.output_var, state='readonly')
        output_entry.grid(row=3, column=0, columnspan=2, sticky=tk.EW)

        output_button = tk.Button(self, text="Browse", command=self.select_output_file)
        output_button.grid(row=3, column=2, padx=10)

        self.translate_button = tk.Button(self, text="Translate", command=self.translate, state=tk.DISABLED)
        self.translate_button.grid(row=4, column=0, columnspan=3, pady=(15, 0))

        self.columnconfigure(1, weight=1)

    def select_input_file(self):
        input_file = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
        if input_file:
            self.input_var.set(input_file)
            self.check_ready_to_translate()

    def select_output_file(self):
        output_file = filedialog.asksaveasfilename(defaultextension='.pdf', filetypes=[("PDF files", "*.pdf")])
        if output_file:
            self.output_var.set(output_file)
            self.check_ready_to_translate()

    def check_ready_to_translate(self):
        if self.input_var.get() and self.output_var.get():
            self.translate_button.config(state=tk.NORMAL)

    def translate(self):
        input_path = self.input_var.get()
        output_path = self.output_var.get()

        pdf_translator = PDFTranslator(input_path, target_language='zh-CN')

        messagebox.showinfo("PDF Translator", "Translating PDF file, please wait...")

        asyncio.run(pdf_translator.translate_and_write_to_pdf(output_path))

        messagebox.showinfo("PDF Translator", f"Translation completed! File saved as: {output_path}")


def main():
    app = TranslatorGUI()
    app.mainloop()


if __name__ == '__main__':
    main()
import os
import textwrap
import openai
import pdfplumber
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from nltk.tokenize import sent_tokenize

pdfmetrics.registerFont(TTFont("SimFang", "simfang.ttf"))

def get_api_keys():
    api_keys = []
    print("Enter your OpenAI API keys, one per line. Type 'EOF' to finish:")
    while True:
        api_key = input()
        if api_key.strip().upper() == "EOF":
            break
        api_keys.append(api_key)
    return api_keys

def get_paragraphs_from_pdf(filepath):
    try:
        paragraphs = []
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    for paragraph in text.split('\n\n'):
                        sentences = sent_tokenize(paragraph)
                        for sentence in sentences:
                            wrapped_lines = textwrap.wrap(sentence, width=50)
                            paragraphs.extend(wrapped_lines)
        return paragraphs
    except FileNotFoundError:
        print(f"File not found: {filepath}")
        return None

def translate_text(text_to_translate, target_language, api_keys):
    translations = []
    current_key_index = 0
    openai.api_key = api_keys[current_key_index]

    for index, line in enumerate(text_to_translate):
        try:
            response = openai.Completion.create(
                engine="text-davinci-003",
                prompt=f"Translate the following English text to {target_language}:\n\n{line}\n",
                max_tokens=200,
                n=1,
                stop=None,
                temperature=0.1,
            )
            translation = response.choices[0].text.strip()
            translations.append(translation)
            print(f"Translated line {index + 1}/{len(text_to_translate)}")
        except openai.error.RateLimitError:
            if current_key_index + 1 < len(api_keys):
                current_key_index += 1
                openai.api_key = api_keys[current_key_index]
            else:
                raise Exception("All API keys have reached their rate limits.")
    return translations

def save_translation_to_pdf(original_text, translated_text, filename):
    doc = SimpleDocTemplate(filename, pagesize=letter)
    elements = []

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Original", fontName="SimFang", fontSize=10))
    styles.add(ParagraphStyle(name="Translated", fontName="SimFang", fontSize=10))

    for original, translated in zip(original_text, translated_text):
        elements.append(Paragraph(original, styles["Original"]))
        elements.append(Spacer(1, 6))
        elements.append(Paragraph(translated, styles["Translated"]))
        elements.append(Spacer(1, 12))

    doc.build(elements)

api_keys = get_api_keys()
input_filename = input("Enter the path of the PDF file you want to translate: ")
target_language = input("Enter the target language (e.g., Chinese, Spanish, French): ")

text_to_translate = get_paragraphs_from_pdf(input_filename)
translated_text = translate_text(text_to_translate, target_language, api_keys)

base_filename = os.path.basename(input_filename)
output_filename = os.path.splitext(base_filename)[0] + "_translated.pdf"
save_translation_to_pdf(text_to_translate, translated_text, output_filename)
print(f"Translation and original text have been saved to {output_filename}")

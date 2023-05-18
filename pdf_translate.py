import os
import json
import textwrap
import openai
import pdfplumber
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import nltk

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
        with pdfplumber.open(filepath) as pdf:
            paragraphs = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    for paragraph in text.split('\n\n'):
                        # Use NLTK's Punkt sentence tokenizer
                        sentences = nltk.tokenize.sent_tokenize(paragraph)
                        for sentence in sentences:
                            wrapped_lines = textwrap.wrap(sentence, width=50)
                            paragraphs.extend(wrapped_lines)
            return paragraphs
    except FileNotFoundError:
        print(f"File not found: {filepath}")
        return None

def translate_text(text_to_translate, target_language, api_keys, start_index=0, start_segment=0):
    translations = []
    current_key_index = 0
    openai.api_key = api_keys[current_key_index]

    try:
        with open('translation_state.json', 'r') as f:
            state = json.load(f)
            start_index = state['index']
            start_segment = state['segment']
            translations = state['translations']
    except FileNotFoundError:
        pass

    for index in range(start_index, len(text_to_translate)):
        paragraph = text_to_translate[index]
        segments = textwrap.wrap(paragraph, width=200)
        for segment_index in range(start_segment, len(segments)):
            segment = segments[segment_index]
            try:
                response = openai.Completion.create(
                    engine="text-davinci-003",
                    prompt=f"Translate the following English text to {target_language}:\n\n{segment}\n",
                    max_tokens=200,
                    n=1,
                    stop=None,
                    temperature=0.1,
                )
                translation = response.choices[0].text.strip()
                translations.append(translation)
                print(f"Translated paragraph {index + 1}/{len(text_to_translate)}")

                with open('translation_state.json', 'w') as f:
                    json.dump({
                        'index': index,
                        'segment': segment_index + 1,
                        'translations': translations,
                    }, f)

            except openai.error.RateLimitError:
                if current_key_index + 1 < len(api_keys):
                    current_key_index += 1
                    openai.api_key = api_keys[current_key_index]
                else:
                    raise Exception("All API keys have been exhausted.")

    os.remove('translation_state.json')

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

input_filepath = input("Enter the path of the PDF file you want to translate: ")

text_to_translate = get_paragraphs_from_pdf(input_filepath)

target_language = input("Enter the target language (e.g., Chinese, Spanish, French): ")

translated_text = translate_text(text_to_translate, target_language, api_keys)

base_name = os.path.basename(input_filepath)
base_name_without_ext = os.path.splitext(base_name)[0]
output_filename = base_name_without_ext + "_translated.pdf"
save_translation_to_pdf(text_to_translate, translated_text, output_filename)

print(f"Translation and original text have been saved to {output_filename}")

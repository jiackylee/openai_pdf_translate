import textwrap
import openai
import pdfplumber
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# 注册字体
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

def get_lines_from_pdf(filename):
    try:
        with pdfplumber.open(filename) as pdf:
            lines = []
            for page in pdf.pages:
                text = page.extract_text()
                for line in text.split('\n'):
                    lines.append(line)
            return lines
    except FileNotFoundError:
        print(f"File not found: {filename}")
        return None

def translate_text(text_to_translate, target_language, api_keys):
    translations = []
    current_key_index = 0
    openai.api_key = api_keys[current_key_index]

    for index, line in enumerate(text_to_translate):
        segments = textwrap.wrap(line, width=200)
        for segment in segments:
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


# 获取用户的API密钥列表
api_keys = get_api_keys()

# 获取要翻译的文件名
input_filename = input("Enter the name of the PDF file you want to translate: ")

# 从PDF文件中获取要翻译的多个行
text_to_translate = get_lines_from_pdf(input_filename)

# 获取目标语言
target_language = input("Enter the target language (e.g., Chinese, Spanish, French): ")

# 翻译文本
translated_text = translate_text(text_to_translate, target_language, api_keys)

# 将原始文本和翻译结果保存到一个PDF文件
output_filename = "translation_result.pdf"
save_translation_to_pdf(text_to_translate, translated_text, output_filename)
print(f"Translation and original text have been saved to {output_filename}")

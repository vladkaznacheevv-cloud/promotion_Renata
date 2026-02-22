# remove_bom.py
with open('models.py', 'rb') as f:
    content = f.read()

if content.startswith(b'\xef\xbb\xbf'):
    content = content[3:]

with open('models.py', 'wb') as f:
    f.write(content)

print("✅ BOM удалён")
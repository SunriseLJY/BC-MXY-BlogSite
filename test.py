from markdown_it import MarkdownIt
md = MarkdownIt()
text = input()
html = md.render(text)
print(html)
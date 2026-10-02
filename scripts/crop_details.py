import PIL.Image as Image

img = Image.open("tmp_live.png")
w, h = img.size
# Crop top left (title bar & navigator)
top_left = img.crop((0, 0, 500, 300))
top_left.save("tmp_top_left.png")
# Crop full toolbox area (y: 800 to 1050)
toolbox = img.crop((0, 750, w, 1050))
toolbox.save("tmp_toolbox.png")
print("Saved top_left and toolbox")

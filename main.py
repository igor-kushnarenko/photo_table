import os

from PIL import Image

WIDTH = 720
x = 330
y = 155


card_path = 'static/card.jpg'
im = Image.open(card_path)

list_path = os.listdir('static/photos')

back_img = im.copy()


def resize_photo(photo_path):
    photo = Image.open(photo_path)
    width, height = photo.size
    new_width = WIDTH
    new_height = int(new_width * height / width)
    photo_resize = photo.resize((new_width, new_height), Image.ANTIALIAS)
    return photo_resize


count = 1
next_name = 1
for file in list_path:
    photo = resize_photo(f'static/photos/{file}')
    back_img.paste(photo, (x, y))
    x += WIDTH
    count += 1
    if count == 5:
        x = 330
        y += 1085
    if count == 9:
        back_img.save(f'new_photo_{next_name}.jpg', quality=100)
        next_name += 1
        count = 1
        x = 330
        y = 155
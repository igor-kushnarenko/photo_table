import os

from PIL import Image, ImageDraw, ImageFont

WIDTH = 720
START_X = 330
START_Y = 155
x = START_X
y = START_Y

im = Image.open('static/card.jpg')
back_img = im.copy()
processing_photos = os.listdir('static/photos')


def resize_photo(photo_path):
    """Функция изменяет размеры изображения сохраняя соотношения сторон."""
    photo = Image.open(photo_path)
    width, height = photo.size
    new_width = WIDTH
    new_height = int(new_width * height / width)
    photo_resize = photo.resize((new_width, new_height), Image.ANTIALIAS)
    return photo_resize


def create_collage():
    """Функция составляет коллажи из фото. """
    global x, y
    if not os.path.exists('static/completed'):
        os.mkdir('static/completed')
    count = 1
    next_name = 1
    for file in processing_photos:
        photo = resize_photo(f'static/photos/{file}')
        back_img.paste(photo, (x, y))
        x += WIDTH
        count += 1
        print('Фото добавлено..')
        if count == 5:
            x = START_X
            y += 1085
        if count == 9:
            back_img.save(f'static/completed/new_photo_{next_name}.jpg', quality=100)
            back_img.show()
            next_name += 1
            count = 1
            x = START_X
            y = START_Y
        if (processing_photos.index(file) + 1) == len(processing_photos):
            back_img.save(f'static/completed/new_photo_{next_name}.jpg', quality=100)
            back_img.show()
            print('Коллажи выполнены!')
            break


if __name__ == '__main__':
    create_collage()
    namer()
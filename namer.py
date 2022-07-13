import os

from PIL import ImageFont, ImageDraw
from PIL import Image


def namer():
    points = (
        (500, 1120), (1250, 1120), (1950, 1120), (2650, 1120),
        (500, 2190), (1250, 2190), (1950, 2190), (2650, 2190),
    )
    font = ImageFont.truetype(font='static/arial.ttf', size=100)
    num_animator = 1
    processing_photos = os.listdir('static/completed')
    for index, photo_name in enumerate(processing_photos):
        if 'new' in photo_name:
            path_image = f'static/completed/{photo_name}'
            image_a4 = Image.open(path_image)
            back_img = image_a4.copy()
            draw_text = ImageDraw.Draw(back_img)
            back_img.show()
            for point in points:
                name_animator = input(f'Введите имя {num_animator} аниматора: ')
                draw_text.text(
                    point,
                    name_animator,
                    fill=('black'),
                    font=font
                )
                num_animator += 1
            back_img.save(f'static/completed/named_photo_{index}.jpg', quality=100)
            back_img.show()
            print('Имена выведены.')


if __name__ == '__main__':
    namer()

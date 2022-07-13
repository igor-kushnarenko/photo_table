from PIL import ImageFont, ImageDraw
from PIL import Image


def namer():
    points = (
        (500, 1120), (1250, 1120), (1950, 1120), (2650, 1120),
        (500, 2190), (1250, 2190), (1950, 2190), (2650, 2190),
    )
    font = ImageFont.truetype(font='/home/max/PycharmProjects/photo_table/static/arial.ttf', size=100)
    path_image = f'/home/max/PycharmProjects/photo_table/static/completed/new_photo_1.jpg'
    image_a4 = Image.open(path_image)
    back_img = image_a4.copy()
    draw_text = ImageDraw.Draw(back_img)
    back_img.show()
    num_animator = 1
    for point in points:
        name_animator = input(f'Введите имя {num_animator} аниматора: ')
        draw_text.text(
            point,
            name_animator,
            fill=('black'),
            font=font
        )
        num_animator += 1
    back_img.save(f'/home/max/PycharmProjects/photo_table/static/completed/named_photo_1.jpg', quality=100)
    back_img.show()
    print('Имена выведены.')


if __name__ == '__main__':
    namer()

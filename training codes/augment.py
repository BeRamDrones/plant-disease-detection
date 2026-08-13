import os
import cv2
import glob
import albumentations as A

TARGET_CLASSES = ["Rice", "Cassava", "Cauliflower", "Mango", "papaya", "peach", "Pumkin"]

BASE_DIR = r"C:\BeRam\plant disease\training1-6"
AUG_PER_IMAGE = 3

transform = A.Compose([
    A.HorizontalFlip(p=0.5),
    A.VerticalFlip(p=0.2),
    A.Rotate(limit=25, p=0.6),
    A.RandomBrightnessContrast(p=0.5),
    A.HueSaturationValue(p=0.4),
    A.MotionBlur(blur_limit=3, p=0.2),
    A.RandomScale(scale_limit=0.15, p=0.4),
    A.CoarseDropout(num_holes_range=(1, 4), hole_height_range=(0.05, 0.1), hole_width_range=(0.05, 0.1), p=0.3),
], bbox_params=A.BboxParams(format='yolo', label_fields=['class_labels']))


def read_labels(label_path):
    boxes, classes = [], []
    if not os.path.exists(label_path):
        return boxes, classes
    with open(label_path, "r") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) != 5:
                continue
            cls, x, y, w, h = parts
            boxes.append([float(x), float(y), float(w), float(h)])
            classes.append(int(cls))
    return boxes, classes


def clip_boxes(boxes):
    clipped = []
    for box in boxes:
        x, y, w, h = box

        x_min = x - w / 2
        y_min = y - h / 2
        x_max = x + w / 2
        y_max = y + h / 2

        x_min = min(max(x_min, 0.0), 1.0)
        y_min = min(max(y_min, 0.0), 1.0)
        x_max = min(max(x_max, 0.0), 1.0)
        y_max = min(max(y_max, 0.0), 1.0)

        new_w = x_max - x_min
        new_h = y_max - y_min
        new_x = x_min + new_w / 2
        new_y = y_min + new_h / 2

        if new_w <= 0 or new_h <= 0:
            continue

        clipped.append([new_x, new_y, new_w, new_h])
    return clipped


def write_labels(label_path, boxes, classes):
    with open(label_path, "w") as f:
        for box, cls in zip(boxes, classes):
            f.write(f"{cls} {' '.join(map(str, box))}\n")


def augment_class(class_name):
    img_dir = os.path.join(BASE_DIR, class_name, "images", "train")
    lbl_dir = os.path.join(BASE_DIR, class_name, "labels", "train")

    # write directly into train folders - no yaml change needed
    out_img_dir = img_dir
    out_lbl_dir = lbl_dir

    progress_file = os.path.join(BASE_DIR, class_name, "augment_progress.txt")
    done_set = set()
    if os.path.exists(progress_file):
        with open(progress_file, "r") as f:
            done_set = set(line.strip() for line in f)

    # only pick original images, skip anything already tagged _aug
    img_paths = [
        p for p in glob.glob(os.path.join(img_dir, "*.*"))
        if "_aug" not in os.path.splitext(os.path.basename(p))[0]
    ]
    print(f"[{class_name}] {len(img_paths)} original images, {len(done_set)} already done")

    progress_f = open(progress_file, "a")

    for img_path in img_paths:
        fname = os.path.splitext(os.path.basename(img_path))[0]

        if fname in done_set:
            continue

        label_path = os.path.join(lbl_dir, fname + ".txt")
        image = cv2.imread(img_path)
        if image is None:
            continue
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        boxes, classes = read_labels(label_path)
        if not boxes:
            continue

        boxes = clip_boxes(boxes)

        for i in range(AUG_PER_IMAGE):
            new_name = f"{fname}_aug{i}"
            out_img_path = os.path.join(out_img_dir, new_name + ".jpg")
            out_lbl_path = os.path.join(out_lbl_dir, new_name + ".txt")

            if os.path.exists(out_img_path) and os.path.exists(out_lbl_path):
                continue

            try:
                augmented = transform(image=image, bboxes=boxes, class_labels=classes)
            except Exception as e:
                print(f"Skip {fname} aug {i}: {e}")
                continue

            aug_img = cv2.cvtColor(augmented["image"], cv2.COLOR_RGB2BGR)
            aug_boxes = augmented["bboxes"]
            aug_classes = augmented["class_labels"]

            if not aug_boxes:
                continue

            cv2.imwrite(out_img_path, aug_img)
            write_labels(out_lbl_path, aug_boxes, aug_classes)

        progress_f.write(fname + "\n")
        progress_f.flush()
        done_set.add(fname)

    progress_f.close()
    print(f"[{class_name}] augmentation done -> {out_img_dir}")


if __name__ == "__main__":
    for cls in TARGET_CLASSES:
        augment_class(cls)
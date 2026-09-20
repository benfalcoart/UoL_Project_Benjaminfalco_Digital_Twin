"""
This is the basic MINC-2500 Material Classification Test

It loads a ResNet18 model trained and fine-tuned using the MINC-2500
material dataset and evaluates arbitrary images placed in the
test_images directory.

Then each image is classified at two spatial scales:

1. The complete source image.
2. Four equally sized quadrants:
    Top Left
    Top Right
    Bottom Left
    Bottom Right

This classifier will report the five most probable MINC material classes
for each region and their confidence percentage.

Purpose:

This script provides a baseline test of the trained material classifier
on images outside the MINC-2500 training and test datasets.

Spatial subdivision is used to investigate: whether local material
classification provides more useful results than classification of an
entire image containing multiple materials.

Experiments with UV texture atlases demonstrate that rectangular
classification regions can contain multiple UV islands, texture
dilation, and unused texture background space. These artifacts SIGNIFICANTLY 
affect the final classification results.
"""

import os

import torch
import torch.nn as nn
from PIL import Image
from torchvision.models import resnet18, ResNet18_Weights


IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".jfif",
    ".bmp",
    ".tif",
    ".tiff"
}

#loads the machine learning model and its class labels.
#rebuild the final fully connected layer to match the number of saved classes.
def load_model(model_path, device):
    checkpoint = torch.load(model_path, map_location=device)

    classes = checkpoint["classes"]

    model = resnet18(weights=None)

    model.fc = nn.Linear(model.fc.in_features, len(classes))

    model.load_state_dict(checkpoint["model_state_dict"])

    model = model.to(device)
    model.eval()

    return model, classes

#Classifies a prepared image using the trained material model and returns the highest probability material predictions in descending order.
def classify_pil_image( image,model,classes,transform,device,top_k=5):
    input_tensor = transform(image.convert("RGB")).unsqueeze(0).to(device)

    with torch.no_grad():
        output = model(input_tensor)

        probabilities = torch.softmax(output, dim=1)[0]

    top_probabilities, top_indices = torch.topk(probabilities, min(top_k, len(classes)))

    results = []

    for probability, index in zip(top_probabilities, top_indices):
        results.append((classes[index.item()], probability.item()))

    return results

#Splits an image into four equally sized rectangular quadrants for independent material classification.
def split_into_quadrants(image):
    width, height = image.size

    mid_x = width // 2
    mid_y = height // 2

    return {
        "Top Left": image.crop((0, 0, mid_x, mid_y)),
        "Top Right": image.crop((mid_x, 0, width, mid_y)),
        "Bottom Left": image.crop((0, mid_y, mid_x, height)),
        "Bottom Right": image.crop((mid_x, mid_y, width, height))
    }

#Prints ranked material predictions and confidence percentages for a classified image region.
def print_results(label, results):
    print(label)

    for rank, (class_name, probability) in enumerate(results, start=1):
        print(f"  {rank}. {class_name:<18} {probability * 100:6.2f}%")

    print()

#Runs the baseline material classification pipeline by loading the trained model and classifying each test image 
#as both a complete image and four quadrants.
def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))

    test_dir = os.path.join(base_dir, "test_images")
    model_path = os.path.join(base_dir, "models", "minc_resnet18.pth")

    #Use GPU if available.
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    print("Device:", device)

    if device.type == "cuda":
        print("GPU:", torch.cuda.get_device_name(0))

    #load the model
    model, classes = load_model(model_path, device)

    weights = ResNet18_Weights.DEFAULT
    transform = weights.transforms()

    image_files = sorted([filename for filename in os.listdir(test_dir) if os.path.splitext(filename)[1].lower() in IMAGE_EXTENSIONS])

    if not image_files:
        print("No supported images found.")
        return

    print()
    print(
        f"Found {len(image_files)} images"
    )
    print()

    for filename in image_files:
        image_path = os.path.join(test_dir, filename)

        try:
            image = Image.open(image_path).convert("RGB")

            print("=" * 80)
            print(filename)
            print("=" * 80)

            whole_results = classify_pil_image( image,model,classes,transform,device)

            print_results("Whole Image", whole_results)

            quadrants = split_into_quadrants(image)

            for quadrant_name, quadrant_image in quadrants.items():
                quadrant_results = classify_pil_image(quadrant_image, model,classes, transform, device)

                print_results(quadrant_name, quadrant_results)

        except Exception as error:
            print("=" * 80)
            print(filename)
            print("=" * 80)
            print(
                "Could not classify:",
                error
            )
            print()


if __name__ == "__main__":
    main()
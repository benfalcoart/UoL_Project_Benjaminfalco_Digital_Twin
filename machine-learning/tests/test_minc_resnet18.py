"""
Evaluates the trained MINC-2500 ResNet18 material classifier using the official MINC test split. 
The script loads the saved model checkpoint and class labels, rebuilds the ResNet18 classification layer, 
and evaluates the model without updating its weights. 

The test reports: 
1. The number of images in the MINC test dataset. 
2. The average cross-entropy loss. 
3. The overall material classification accuracy. 
4. The total execution time required to evaluate the test set. 

Purpose: This script provides a final evaluation of the trained material classification model 
using data that was not used during training or validation. 
The resulting test accuracy provides an estimate of how well the fine-tuned ResNet18 model generalizes 
to unseen MINC-2500 samples. 
"""

import os

import torch
import torch.nn as nn
from torch.utils.data import DataLoader
from torchvision.models import resnet18, ResNet18_Weights

from finetune_minc_resnet18 import MINCDataset, run_epoch

# Loads the saved material classifier and evaluates it using the # official MINC-2500 test dataset.
def main():
    base_dir = os.path.dirname(
        os.path.abspath(__file__)
    )

    dataset_dir = os.path.join(
        base_dir,
        "data",
        "minc-2500"
    )

    test_split = os.path.join(
        dataset_dir,
        "labels",
        "test1.txt"
    )

    model_path = os.path.join(
        base_dir,
        "models",
        "minc_resnet18.pth"
    )

    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    checkpoint = torch.load(
        model_path,
        map_location=device
    )

    classes = checkpoint["classes"]

    weights = ResNet18_Weights.DEFAULT
    transform = weights.transforms()

    test_dataset = MINCDataset(
        root=dataset_dir,
        split_file=test_split,
        transform=transform,
        classes=classes
    )

    test_loader = DataLoader(
        test_dataset,
        batch_size=64,
        shuffle=False,
        num_workers=4,
        pin_memory=device.type == "cuda",
        persistent_workers=True
    )

    model = resnet18(
        weights=None
    )

    model.fc = nn.Linear(
        model.fc.in_features,
        len(classes)
    )

    model.load_state_dict(
        checkpoint["model_state_dict"]
    )

    model = model.to(device)

    criterion = nn.CrossEntropyLoss()

    test_loss, test_accuracy, test_time = run_epoch(
        model=model,
        loader=test_loader,
        criterion=criterion,
        device=device
    )

    print()
    print("MINC Test Results")
    print("-============================-")
    print(f"Images: {len(test_dataset)}")
    print(f"Loss: {test_loss:.4f}")
    print(f"Accuracy: {test_accuracy * 100:.2f}%")
    print(f"Time: {test_time:.2f} seconds")


if __name__ == "__main__":
    main()
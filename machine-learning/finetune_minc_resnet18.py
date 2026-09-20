import os
import time
from PIL import Image

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torchvision.models import resnet18, ResNet18_Weights

"""
This is a custom PyTorch dataset for loading images and material class labels 
from the MINC-2500 dataset split files.
"""
class MINCDataset(Dataset):
    def __init__(self, root, split_file, transform=None, classes=None):
        self.root = root
        self.transform = transform

        with open(split_file, "r") as file:
            self.paths = [
                line.strip()
                for line in file
                if line.strip()
            ]

        if classes is None:
            self.classes = sorted({
                path.split("/")[1]
                for path in self.paths
            })
        else:
            self.classes = classes

        self.class_to_idx = {
            class_name: index
            for index, class_name in enumerate(self.classes)
        }
    """
    Returns the total number of images contained in this dataset.
    """
    def __len__(self):
        return len(self.paths)

    """
    Loads and preprocesses a single image and returns it with its corresponding material class label.
    """
    def __getitem__(self, index):
        relative_path = self.paths[index]
        image_path = os.path.join(self.root, relative_path)

        class_name = relative_path.split("/")[1]
        label = self.class_to_idx[class_name]

        image = Image.open(image_path).convert("RGB")

        if self.transform:
            image = self.transform(image)

        return image, label

"""
Runs one complete training or validation epoch.When an optimizer is provided, gradients are 
calculated and the model weights are updated. Otherwise, the model is evaluated without training!
Returns the average loss, classification accuracy, and execution time.
"""
def run_epoch(model, loader, criterion, device, optimizer=None):
    training = optimizer is not None

    if training:
        model.train()
    else:
        model.eval()

    total_loss = 0.0
    total_correct = 0
    total_samples = 0

    start_time = time.perf_counter()

    for batch_index, (images, labels) in enumerate(loader):
        images = images.to(device, non_blocking=True)

        labels = labels.to(device, non_blocking=True)

        if training:
            optimizer.zero_grad()

        with torch.set_grad_enabled(training):
            outputs = model(images)
            loss = criterion(outputs, labels)

            if training:
                loss.backward()
                optimizer.step()

        total_loss += loss.item() * images.size(0)

        predictions = outputs.argmax(dim=1)

        total_correct += (
            predictions == labels
        ).sum().item()

        total_samples += images.size(0)

        if training and (batch_index + 1) % 100 == 0:
            print(
                f"Batch {batch_index + 1}/{len(loader)}"
            )

    if device.type == "cuda":
        torch.cuda.synchronize()

    elapsed = time.perf_counter() - start_time

    average_loss = total_loss / total_samples
    accuracy = total_correct / total_samples

    return average_loss, accuracy, elapsed
"""
Configures the MINC-2500 datasets, ResNet-18 model, training parameters, and hardware device 
before fine-tuning the model, and then saving the checkpoint with the highest validation accuracy.
"""
def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dataset_dir = os.path.join(base_dir, "data", "minc-2500")

    train_split = os.path.join(dataset_dir, "labels", "train1.txt")
    validation_split = os.path.join(dataset_dir, "labels", "validate1.txt")

    model_dir = os.path.join(base_dir, "models")
    os.makedirs(model_dir, exist_ok=True)
    model_path = os.path.join(model_dir, "minc_resnet18.pth")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    print("PyTorch:", torch.__version__)
    print("Device:", device)

    if device.type == "cuda":
        print("GPU:", torch.cuda.get_device_name(0))

    #Load the ImageNet pretrained ResNet-18 architecture and preprocessing pipeline.
    weights = ResNet18_Weights.DEFAULT
    transform = weights.transforms()

    train_dataset = MINCDataset(root=dataset_dir, split_file=train_split, transform=transform)

    validation_dataset = MINCDataset(root=dataset_dir, split_file=validation_split, transform=transform, classes=train_dataset.classes)

    print()
    print("Classes:", len(train_dataset.classes))
    print("Training images:", len(train_dataset))
    print("Validation images:", len(validation_dataset))

    batch_size = 64
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True,
        num_workers=4,
        pin_memory=device.type == "cuda",
        persistent_workers=True
    )

    validation_loader = DataLoader(validation_dataset, batch_size=batch_size,shuffle=False,
        num_workers=4,
        pin_memory=device.type == "cuda",
        persistent_workers=True
    )

    model = resnet18(weights=weights)

    #Freezes the pretrained feature extractor, then fine-tune the final
    #residual block and a new classification layer for the MINC classes.
    for parameter in model.parameters():
        parameter.requires_grad = False

    for parameter in model.layer4.parameters():
        parameter.requires_grad = True

    model.fc = nn.Linear(model.fc.in_features, len(train_dataset.classes))

    model = model.to(device)

    criterion = nn.CrossEntropyLoss()

    optimizer = torch.optim.Adam(filter(lambda parameter: parameter.requires_grad, model.parameters()), lr=0.0001)
    #Load the previously trained model parameters before continuing fine-tuning for the configured number of epochs.
    checkpoint = torch.load(model_path, map_location=device)

    model.load_state_dict(checkpoint["model_state_dict"])
    epochs = 5

    best_validation_accuracy = 0.0

    print()
    print("Starting training")
    print("======================")

    for epoch in range(epochs):
        print()
        print(f"Epoch {epoch + 1}/{epochs}")

        train_loss, train_accuracy, train_time = run_epoch( model=model, loader=train_loader, criterion=criterion, device=device, optimizer=optimizer)
        validation_loss, validation_accuracy, validation_time = run_epoch( model=model, loader=validation_loader, criterion=criterion, device=device)

        print(f"Train Loss: {train_loss:.4f}")
        print(f"Train Accuracy: {train_accuracy * 100:.2f}%")
        print(f"Validation Loss: {validation_loss:.4f}")
        print(f"Validation Accuracy: {validation_accuracy * 100:.2f}%")

        print(f"Train Time: {train_time / 60:.2f} min")

        print(f"Validation Time: {validation_time / 60:.2f} min")

        #Save a new checkpoint when the current model achieves a higher validation accuracy 
        #than previous epochs in this training run...
        if validation_accuracy > best_validation_accuracy:
            best_validation_accuracy = validation_accuracy

            torch.save(
                {
                    "model_state_dict":
                        model.state_dict(),

                    "classes":
                        train_dataset.classes,

                    "validation_accuracy":
                        validation_accuracy
                },
                model_path
            )

            print("Saved new best model:", model_path)

    print()
    print("======================")
    print("Training complete")

    print(f"Best validation accuracy: {best_validation_accuracy * 100:.2f}%")

    print("Best model saved to:", model_path)


if __name__ == "__main__":
    main()
import os
import random
import time
from PIL import Image

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms
from torchvision.models import resnet18, ResNet18_Weights


class DMSDataset(Dataset):
    def __init__(self, root, split, transform=None, classes=None):
        self.root = os.path.join(root, split)
        self.transform = transform
        self.classes = classes or sorted(name for name in os.listdir(self.root) if os.path.isdir(os.path.join(self.root, name)) and any(filename.lower().endswith(".jpg") for filename in os.listdir(os.path.join(self.root, name))))
        self.class_to_idx = {name: index for index, name in enumerate(self.classes)}
        self.samples = []

        for class_name in self.classes:
            folder = os.path.join(self.root, class_name)
            if not os.path.isdir(folder):
                continue
            for filename in sorted(os.listdir(folder)):
                if filename.lower().endswith(".jpg"):
                    self.samples.append((os.path.join(folder, filename), self.class_to_idx[class_name]))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, index):
        image_path, label = self.samples[index]
        with Image.open(image_path) as source:
            image = source.convert("RGB")
        if self.transform:
            image = self.transform(image)
        return image, label


def run_epoch(model, loader, criterion, device, optimizer=None, scaler=None):
    training = optimizer is not None
    model.train(training)
    total_loss = 0.0
    total_correct = 0
    total_samples = 0
    start_time = time.perf_counter()

    for batch_index, (images, labels) in enumerate(loader):
        images = images.to(device, non_blocking=True)
        labels = labels.to(device, non_blocking=True)
        if training:
            optimizer.zero_grad(set_to_none=True)

        with torch.set_grad_enabled(training):
            with torch.autocast(device_type=device.type, enabled=device.type == "cuda"):
                outputs = model(images)
                loss = criterion(outputs, labels)
            if training:
                scaler.scale(loss).backward()
                scaler.step(optimizer)
                scaler.update()

        total_loss += loss.item() * images.size(0)
        total_correct += (outputs.argmax(dim=1) == labels).sum().item()
        total_samples += images.size(0)
        if training and (batch_index + 1) % 100 == 0:
            print(f"Batch {batch_index + 1}/{len(loader)}")

    if device.type == "cuda":
        torch.cuda.synchronize()
    elapsed = time.perf_counter() - start_time
    return total_loss / total_samples, total_correct / total_samples, elapsed


def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dataset_dir = os.path.join(base_dir, "data", "dms_resnet18_v2")
    model_dir = os.path.join(base_dir, "models")
    os.makedirs(model_dir, exist_ok=True)
    model_path = os.path.join(model_dir, "dms_resnet18.pth")

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("PyTorch:", torch.__version__)
    print("Device:", device)
    if device.type == "cuda":
        print("GPU:", torch.cuda.get_device_name(0))

    random.seed(42)
    torch.manual_seed(42)
    if device.type == "cuda":
        torch.cuda.manual_seed_all(42)

    weights = ResNet18_Weights.DEFAULT
    train_transform = transforms.Compose([
        transforms.RandomResizedCrop(224, scale=(0.75, 1.0)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomVerticalFlip(),
        transforms.RandomRotation(180),
        transforms.ColorJitter(brightness=0.15, contrast=0.15, saturation=0.1),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])
    validation_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
    ])

    train_dataset = DMSDataset(root=dataset_dir, split="train", transform=train_transform)
    validation_dataset = DMSDataset(root=dataset_dir, split="validation", transform=validation_transform, classes=train_dataset.classes)
    test_dataset = DMSDataset(root=dataset_dir, split="test", transform=validation_transform, classes=train_dataset.classes)
    if min(len(train_dataset), len(validation_dataset), len(test_dataset)) == 0:
        raise ValueError("DMS requires non-empty train, validation, and test splits")

    print()
    print("Classes:", len(train_dataset.classes))
    print("Training images:", len(train_dataset))
    print("Validation images:", len(validation_dataset))
    print("Test images:", len(test_dataset))

    batch_size = 32
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=0, pin_memory=device.type == "cuda")
    validation_loader = DataLoader(validation_dataset, batch_size=batch_size, shuffle=False, num_workers=0, pin_memory=device.type == "cuda")
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False, num_workers=0, pin_memory=device.type == "cuda")

    model = resnet18(weights=weights)
    model.fc = nn.Linear(model.fc.in_features, len(train_dataset.classes))
    model = model.to(device)

    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.0001, weight_decay=0.0001)
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    epochs = 10
    best_validation_accuracy = -1.0

    print()
    print("Starting training")
    print("======================")

    for epoch in range(epochs):
        print()
        print(f"Epoch {epoch + 1}/{epochs}")
        train_loss, train_accuracy, train_time = run_epoch(model, train_loader, criterion, device, optimizer, scaler)
        validation_loss, validation_accuracy, validation_time = run_epoch(model, validation_loader, criterion, device)

        print(f"Train Loss: {train_loss:.4f}")
        print(f"Train Accuracy: {train_accuracy * 100:.2f}%")
        print(f"Validation Loss: {validation_loss:.4f}")
        print(f"Validation Accuracy: {validation_accuracy * 100:.2f}%")
        print(f"Train Time: {train_time / 60:.2f} min")
        print(f"Validation Time: {validation_time / 60:.2f} min")

        if validation_accuracy > best_validation_accuracy:
            best_validation_accuracy = validation_accuracy
            torch.save({"model_state_dict": model.state_dict(), "classes": train_dataset.classes, "validation_accuracy": validation_accuracy}, model_path)
            print("Saved new best model:", model_path)

    checkpoint = torch.load(model_path, map_location=device, weights_only=True)
    model.load_state_dict(checkpoint["model_state_dict"])
    test_loss, test_accuracy, test_time = run_epoch(model, test_loader, criterion, device)

    print()
    print("======================")
    print("Training complete")
    print(f"Best validation accuracy: {best_validation_accuracy * 100:.2f}%")
    print(f"Test loss: {test_loss:.4f}")
    print(f"Test accuracy: {test_accuracy * 100:.2f}%")
    print(f"Test time: {test_time / 60:.2f} min")
    print("Best model saved to:", model_path)


if __name__ == "__main__":
    main()

class Animal {
  speak(): string {
    return "???";
  }
}

class Dog extends Animal {
  speak(): string {
    return "Woof!";
  }
}

function makeSound(animal: Animal): void {
  console.log(animal.speak());
}
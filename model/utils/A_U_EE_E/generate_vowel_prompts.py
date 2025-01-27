import random

vowels = ['A', 'U', 'EE', 'E']
repetitions = 30
sequence = []

# Generate the sequence with no consecutive repetition
prev_vowel = None
for _ in range(repetitions * len(vowels)):
    available_vowels = [vowel for vowel in vowels if vowel != prev_vowel]
    next_vowel = random.choice(available_vowels)
    sequence.append(next_vowel)
    prev_vowel = next_vowel

# Write to file, forming sentence-like structures
with open("vowel_recording_script.txt", "w") as file:
    sentence_length = 5  # Target length for each 'sentence'
    current_sentence = []

    line_number = 1
    for vowel in sequence:
        current_sentence.append(vowel)
        if len(current_sentence) == sentence_length:
            file.write(f"{line_number}.\t" + " ".join(current_sentence) + ".\n")  # End the sentence
            current_sentence = []
            line_number += 1
            sentence_length = random.randint(4, 8)  # Random sentence length for the next sentence

    # If there are leftover vowels at the end, form a final sentence
    if current_sentence:
        file.write(f"{line_number}.\t" + " ".join(current_sentence) + ".\n")

print("Randomized vowel text with sentence-like structure has been generated.")

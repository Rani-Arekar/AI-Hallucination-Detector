// These are example PROMPTS (questions), not pre-written answers -- the
// backend generates its own answer from whatever is submitted here, then
// verifies that generated answer. The labels describe what kind of answer
// the question tends to produce, as a hint for what to expect, not a
// guarantee (the actual AI answer, and its verification result, can vary
// between runs).
export const examplePrompts = [
  {
    label: "Straightforward",
    text: "When was the Eiffel Tower built, and how tall is it?",
  },
  {
    label: "Prone to myths",
    text: "Is the Great Wall of China visible from space with the naked eye?",
  },
  {
    label: "Mixed / opinionated",
    text: "Who created Python, when was it released, and is it the fastest programming language?",
  },
] as const

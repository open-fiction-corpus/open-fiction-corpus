# Training guide

The corpus is designed first for causal-language-model continued pretraining on complete fiction.

Load complete documents, tokenize with the chosen base model's tokenizer, append that tokenizer's real EOS token, and create contiguous context windows without crossing document boundaries unless the training framework supplies document-aware packing.

Do not hard-code `<|endoftext|>` or any other literal token unless it is verified as a special token for the selected tokenizer.

Raw-book continued pretraining teaches prose continuation. It does not by itself teach a model to convert outlines into scenes. Projects needing controlled outline-to-prose generation should use a separate, smaller task-tuning stage with non-conversational plan/prose examples.

Keep evaluation works out of the training split and record every corpus release, model checkpoint, tokenizer, context length, packing strategy, learning rate, and seed.

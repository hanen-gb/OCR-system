import kagglehub

# Download latest version
path = kagglehub.model_download("<KAGGLE_USER>/layoutxlm-finetuned-invoices/transformers/transformers")

print("Path to model files:", path)
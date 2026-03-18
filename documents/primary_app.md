# Primary App Selection

## Selected App

- App Name: ChatGPT
- Platform: Google Play Store
- App ID: com.openai.chatgpt
- Store Link: https://play.google.com/store/apps/details?id=com.openai.chatgpt

## Selection Rationale

This application is selected as the **primary target source** for Phase I ingestion validation.

Key reasons:

1. **Supervisor recommendation**
   - The ChatGPT app was explicitly suggested by John as a strong candidate source.

2. **High review volume**
   - The app has a large and continuously growing number of user reviews, making it suitable for validating ingestion at the 10k+ scale.

3. **Rich sentiment signal**
   - Reviews typically include:
     - Rating score
     - Free-text feedback
     - Timestamp
     - Helpful votes

   This structure aligns well with the downstream sentiment analysis goals.

4. **Product relevance**
   - The app is directly related to the AI product domain, making the dataset commercially meaningful.

## Scope Note

For Phase I, this app is **frozen as the primary ingestion target**.

Unless significant technical issues arise during ingestion (e.g., blocking anti-scraping behavior), the project will proceed using this source for the pilot and 10k-scale collection milestone.

## Next Steps

1. Define schema and deduplication rules for reviews.
2. Implement ingestion workflow for this app.
3. Run a pilot collection (~1k reviews) to validate the pipeline.
4. Expand to the full milestone collection (≥10k reviews).
# Primary App Selection

Historical note: this file records the original Phase I source-selection decision. The selection itself remains valid historical context, but the project has since progressed through an accepted Phase II closed loop.

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

The step list originally tied to this Phase I selection is now historically superseded.

Current bounded next step, if work continues beyond accepted Phase II: keep any follow-on analysis limited to a tightly controlled reviewer-insight layer over high-confidence `other` and low-confidence predictions, without changing the accepted closed-loop workflow or expanding the formal label set.
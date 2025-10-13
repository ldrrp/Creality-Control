# Product Images

This directory contains product images for various Creality printer models.

## Naming Convention

Images should be named according to the printer model using the following format:

**Format**: `{MODEL_NAME}.webp`

**Examples**:
- `K1_SE.webp` for Creality K1SE
- `K1C.webp` for Creality K1C  
- `ENDER_3_V3_SE.webp` for Creality Ender-3 V3 SE
- `HALOT_ONE.webp` for Creality Halot-One

**Note**: The exact model name reported by each printer may vary. Check the integration logs to see what model name is detected, then name your image file accordingly.

## Image Requirements

- **Format**: WebP (preferred)
- **Size**: Recommended 300x300px or larger
- **Quality**: High resolution, clear product images
- **Content**: Official product photos or high-quality renders

## Adding New Images

1. Find or create a high-quality product image for the printer model with transparent background
2. Name the file according to the convention above as webp
3. Place it in this directory
4. The integration will automatically detect and use the image based on the detected printer model

## Fallback

If no specific image is found for a printer model, the integration will fall back to showing no product image rather than displaying a broken image.

# Heroku Deployment for PDF OCR

To deploy the application with PDF OCR capability to Heroku, follow these additional steps:

## 1. Add Required Buildpacks

```bash
# Add the apt buildpack to install system dependencies
heroku buildpacks:add --index 1 https://github.com/heroku/heroku-buildpack-apt

# Make sure the Python buildpack is also present
heroku buildpacks:add heroku/python
```

## 2. Configure Redis

```bash
# Add the Redis add-on for Celery
heroku addons:create heroku-redis:hobby-dev
```

## 3. Configure Environment Variables

```bash
# PDF Processing Configuration
heroku config:set PDF_BATCH_COMMIT_SIZE=10
heroku config:set PDF_USE_SINGLE_TRANSACTION=false
heroku config:set PDF_MAX_ERROR_PERCENTAGE=10.0

# Tesseract Configuration
heroku config:set TESSERACT_PATH=/app/.apt/usr/bin/tesseract
heroku config:set TESSERACT_LANGUAGES=eng
```

## 4. Scale Workers

After deploying, scale the Celery worker dyno:

```bash
heroku ps:scale worker=1
```

## 5. Monitoring

Monitor your Celery workers:

```bash
# View worker logs
heroku logs --tail --dyno worker

# Check dyno status
heroku ps
```

## 6. Troubleshooting

If OCR is not working properly:

1. Check if the worker process is running: `heroku ps`
2. Examine worker logs: `heroku logs --tail --dyno worker`
3. Verify system dependencies were installed: `heroku run ls -la /app/.apt/usr/bin/tesseract`
4. Test OCR manually: `heroku run python -c "import pytesseract; print(pytesseract.get_tesseract_version())"` 
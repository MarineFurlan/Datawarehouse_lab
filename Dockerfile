FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY dbt_project.yml .
COPY macros ./macros
COPY models ./models
COPY tests ./tests
COPY profiles ./profiles

ENTRYPOINT ["dbt"]
CMD ["build", "--profiles-dir", "/app/profiles"]
# Gunakan Python 3.9 sebagai base image (sesuai README)
FROM python:3.9-slim

# Set working directory di dalam container
WORKDIR /app

# Install system dependencies yang diperlukan
# git: diperlukan untuk beberapa library python yang install dari git
# curl: untuk healthcheck atau debugging
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements.txt terlebih dahulu untuk caching layer
COPY requirements.txt .

# Install Python dependencies
# --no-cache-dir untuk mengurangi ukuran image
RUN pip install --no-cache-dir -r requirements.txt

# Copy seluruh kode aplikasi
COPY . .

# Set PYTHONPATH agar modul src bisa ditemukan
ENV PYTHONPATH=/app

# Buat direktori untuk downloads agar permission-nya benar
RUN mkdir -p downloads

# Expose port default Streamlit
EXPOSE 8501

# Healthcheck untuk memastikan aplikasi berjalan
HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Command untuk menjalankan aplikasi
ENTRYPOINT ["streamlit", "run", "src/ui/app.py", "--server.port=8501", "--server.address=0.0.0.0"]

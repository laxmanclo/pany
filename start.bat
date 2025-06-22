@echo off
REM Pany Multi-Modal Vector Database - Quick Start Script for Windows

echo 🚀 Starting Pany Multi-Modal Vector Database...
echo ================================================

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker is not running. Please start Docker and try again.
    exit /b 1
)

REM Check if docker-compose is available
docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo ❌ docker-compose not found. Please install docker-compose.
    exit /b 1
)

echo 📦 Building and starting services...
docker-compose up --build -d

echo ⏳ Waiting for services to be ready...
timeout /t 10 /nobreak >nul

REM Wait for database to be ready
echo 🔍 Checking database connection...
set max_attempts=30
set attempt=1

:db_check_loop
docker exec pany_postgres pg_isready -U pany_user -d pany_vectordb >nul 2>&1
if not errorlevel 1 (
    echo ✅ Database is ready!
    goto db_ready
)

if %attempt% geq %max_attempts% (
    echo ❌ Database failed to start after %max_attempts% attempts
    docker-compose logs database
    exit /b 1
)

echo    Attempt %attempt%/%max_attempts% - waiting...
timeout /t 2 /nobreak >nul
set /a attempt+=1
goto db_check_loop

:db_ready

REM Wait for embedding service to be ready
echo 🔍 Checking embedding service...
set max_attempts=30
set attempt=1

:api_check_loop
curl -s http://localhost:8000/health >nul 2>&1
if not errorlevel 1 (
    echo ✅ Embedding service is ready!
    goto api_ready
)

if %attempt% geq %max_attempts% (
    echo ❌ Embedding service failed to start after %max_attempts% attempts
    docker-compose logs embedding-service
    exit /b 1
)

echo    Attempt %attempt%/%max_attempts% - waiting...
timeout /t 3 /nobreak >nul
set /a attempt+=1
goto api_check_loop

:api_ready

echo.
echo 🎉 Pany Multi-Modal Vector Database is ready!
echo ================================================
echo.
echo 📊 Service Status:
echo    • Database: http://localhost:5432 (pany_vectordb)
echo    • API: http://localhost:8000
echo    • Documentation: http://localhost:8000/docs
echo    • Health Check: http://localhost:8000/health
echo.
echo 🚀 NEW: Super Simple SaaS Interface:
echo    • Dashboard: Open dashboard.html in your browser
echo    • Upload API: POST /upload (drag & drop files)
echo    • Search API: POST /simple-search (just send query)
echo    • Widget: Copy/paste embed code like Google Analytics
echo.
echo 🧪 Quick Test:
echo    cd examples ^&^& python simple_demo.py
echo.
echo 📝 Old API Testing:
echo    cd examples ^&^& python test_api.py
echo.
echo 🔗 Embed Widget:
echo    ^<script src="http://localhost:8000/widget.js" data-project="demo-project"^>^</script^>
echo.
echo 🛑 To stop:
echo    docker-compose down
echo.
echo 🗂️  Database Access:
echo    docker exec -it pany_postgres psql -U pany_user -d pany_vectordb
echo.

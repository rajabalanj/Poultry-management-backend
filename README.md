# Poultry Management System

A comprehensive management system for poultry operations, designed to streamline daily operations, track inventory, manage sales and purchases, and generate detailed reports.

## Features

- **Batch Management**: Track and manage poultry batches with detailed performance metrics
- **Inventory Control**: Monitor and manage feed, medicine, and other inventory items
- **Purchase Orders**: Create and track purchase orders for supplies and equipment
- **Sales Management**: Handle sales orders and payments efficiently
- **Financial Reporting**: Generate comprehensive financial reports for business insights
- **Daily Operations**: Track daily batch activities and performance metrics
- **Business Partner Management**: Maintain records of suppliers and customers
- **Composition Management**: Create and manage feed compositions
- **Operational Expense Tracking**: Monitor and categorize operational expenses

## Technology Stack

- **Backend**: FastAPI, SQLAlchemy, PostgreSQL
- **Frontend**: React JS, Bootstrap CSS, Axios
- **Database**: PostgreSQL
- **Authentication**: JWT (JSON Web Tokens)
- **Containerization**: Docker

## Installation

### Prerequisites

- Python 3.10+
- PostgreSQL database
- Docker (optional, for containerized deployment)

### Backend Setup

1. Clone the repository:

   ```bash
   git clone <repository-url>
   cd Poultry-Management/backend
   ```

2. Create a virtual environment:

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Set up environment variables:
   Create a `.env` file with the following variables:

   ```ini
   POSTGRES_USER=your_db_user
   POSTGRES_PASSWORD=your_db_password
   POSTGRES_SERVER=localhost
   POSTGRES_PORT=5432
   POSTGRES_DB=poultry_db
   CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
   ```

5. Run database migrations:

   ```bash
   alembic upgrade head
   ```

6. Start the backend server:

   ```bash
   uvicorn main:app --reload
   ```

### Frontend Setup

1. Navigate to the frontend directory:

   ```bash
   cd ../frontend
   ```

2. Install dependencies:

   ```bash
   npm install
   ```

3. Start the development server:

   ```bash
   npm run dev
   ```

## Docker Deployment

To run the application using Docker:

1. Build and start the containers:

   ```bash
   cd backend
   docker-compose up --build
   ```

2. The API will be available at `http://localhost:8000`

## API Documentation

Once the backend is running, you can access the interactive API documentation at:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Project Structure

```text
Poultry-Management/
├── backend/
│   ├── main.py              # FastAPI application entry point
│   ├── database.py          # Database configuration
│   ├── models/              # SQLAlchemy models
│   ├── routers/             # API route handlers
│   ├── schemas/             # Pydantic schemas
│   ├── crud/                # Database operations
│   ├── utils/               # Utility functions
│   └── tests/               # Backend tests
├── frontend/
│   └── src/                 # Frontend source code
└── README.md                # This file
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

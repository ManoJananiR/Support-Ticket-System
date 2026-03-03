# Support Ticket System

A comprehensive, production-ready support ticket system built with Django and MySQL. This system provides complete ticket management with role-based access control, email notifications, SLA monitoring, and a REST API.

## Features

### Core Functionality
- **Ticket Management**: Create, view, update, and track support tickets
- **Role-Based Access**: Customer, Agent, and Admin roles with appropriate permissions
- **Comment System**: Public replies and internal notes with file attachments
- **Email Notifications**: Automated email alerts for ticket events
- **SLA Monitoring**: Track response and resolution times with breach alerts
- **Advanced Filtering**: Search and filter tickets by multiple criteria
- **Dashboard**: Statistics and charts for ticket analytics
- **Bulk Operations**: Perform actions on multiple tickets simultaneously

### Security Features
- Password hashing with bcrypt/argon2
- Rate limiting on authentication endpoints
- Content Security Policy (CSP) headers
- CSRF protection
- XSS prevention
- SQL injection protection
- Account lockout after failed attempts
- Two-factor authentication ready

### API
- RESTful API with JWT authentication
- Full CRUD operations for tickets
- Filtering, searching, and pagination
- Rate limiting on API endpoints

## Technology Stack

- **Backend**: Django 4.2.7
- **Database**: MySQL 8.0+
- **Frontend**: Bootstrap 5, jQuery, Chart.js
- **Task Queue**: Celery with Redis
- **API**: Django REST Framework
- **Authentication**: JWT + Session

## Installation

### Prerequisites
- Python 3.9+
- MySQL 8.0+
- Redis (for Celery)
- Git

### Step 1: Clone the Repository
```bash
git clone https://github.com/yourusername/support-ticket-system.git
cd support-ticket-system
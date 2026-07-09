

# Hospital Management System — Implementation Plan

This will **replace the current AI Outreach System** entirely with a Hospital Management System built in React + Tailwind CSS. Since Lovable cannot run Node.js/Express/MongoDB, the backend will be simulated with local state and API-ready service functions that can be swapped for real endpoints later.

## Theme
- **Colors**: White + Blue (#3b82f6) + Green (#10b981) gradients
- **Style**: Cards with soft shadows, rounded corners, smooth hover animations

## What Will Be Built

### Auth System
- `HospitalAuthContext.tsx` — manages user state with 3 roles: Admin, Doctor, Patient
- Role-based `ProtectedRoute` redirecting to correct dashboard

### Public Pages (before login)
1. **Landing Page** (`/`) — Navbar, Hero ("Book Your Doctor Appointment Easily"), Doctors preview grid, Services cards, About section, Contact, Footer
2. **Login Page** (`/login`) — Split-screen: left illustration area, right form with email, password, role dropdown, show/hide toggle, validation, gradient button
3. **Signup Page** (`/signup`) — Same split-screen style with name, email, password, role fields

### Patient Dashboard (`/patient/*`)
- Sidebar: Dashboard, Doctors, My Appointments, Logout
- **Dashboard**: Welcome + stats cards
- **Doctors**: Browse doctors, view availability, book slot
- **My Appointments**: Table with Cancel button

### Doctor Dashboard (`/doctor/*`)
- Sidebar: Dashboard, Set Availability, My Schedule, Logout
- **Set Availability**: Add/delete time slots (date + time picker)
- **My Schedule**: View booked appointments (read-only)

### Admin Dashboard (`/admin/*`)
- Sidebar: Dashboard, Doctors, Appointments, Patients, Logout
- **Dashboard**: Cards (Total Doctors, Patients, Bookings Today)
- **Doctors**: Manage doctors table
- **Appointments**: View all, Mark as Visited, Delete
- **Patients**: Patient list

### Data Layer
- `services/api.ts` — API-ready functions matching all specified endpoints (auth, doctors, availability, appointments)
- Local state management simulating booking logic (slot unavailable after booking, no double booking, Booked/Visited status)

### Files Changed/Created (~20 files)
- Delete/replace all AI Outreach pages and components
- New context, layouts, pages, and service files for HMS


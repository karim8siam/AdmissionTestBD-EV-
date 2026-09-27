# 🎓 AdmissionTestBD (English Version - EV)

Full-length, AI-powered Medical & University Admission Mock Test Platform designed specifically for English Version (NCTB EV) and English Medium candidates in Bangladesh.

---

## 🌟 Key Features

1. **Medical 100 Full-Length Model Tests**:
   - **Tests 1 to 5 are 100% Free!**
   - **Tests 6 to 100** (95 Premium Tests) available for **৳499**.
   - Standard BMDC/DGHS Syllabus Breakdown:
     - **Biology (Botany & Zoology)**: 30 Questions
     - **Chemistry (1st & 2nd Paper)**: 25 Questions
     - **Physics (1st & 2nd Paper)**: 20 Questions
     - **English**: 15 Questions
     - **General Knowledge**: 10 Questions
     - **Strictly Zero Mathematics**.
   - Full 100-mark OMR simulation with negative marking (-0.25).

2. **Varsity & GST Science 100 Model Tests**:
   - **Tests 1 to 5 are 100% Free!**
   - **Tests 6 to 100** available for **৳499**.
   - Dhaka University (DU A Unit) & GST Integrated Science Syllabus:
     - **Physics**: 25 Questions
     - **Chemistry**: 25 Questions
     - **Higher Mathematics**: 25 Questions
     - **Biology**: 25 Questions

3. **Mega Combo Package (Medical + Varsity)**:
   - Complete access to all 200 model tests for a one-time fee of **৳799**.

4. **Sequential Lock & Unlimited Retakes**:
   - Sequential lock ensures consistent step-by-step preparation (completing Test $N-1$ unlocks Test $N$).
   - Any unlocked test can be retaken unlimited times with fresh scoring.

5. **Past 15 Years Question Archive (2010–2025)**:
   - Authentic past question papers from Medical and DU/GST admission exams in English.
   - Timed exam mode and instant answer key mode.

6. **2,000+ NCTB Textbook Knowledge Base (EV)**:
   - Verified formulas, laws, exceptions, and textbook citations from standard NCTB English Version textbooks (Dr. Abul Hasan Botany, Prof. Gazi Azmal Zoology, Hazari & Nag Chemistry, Dr. Tapan Physics, Ketab Uddin Higher Math).

7. **DU 'Ka' Unit No-Calculator Speed Math Engine**:
   - Scientific mental calculation shortcuts for logarithms, square roots, limits, and integration in under 15 seconds.

8. **Automated bKash Payment & Live National Merit Leaderboard**:
   - Instant automated verification via bKash TrxID matching.
   - Live Session Rank and All-Bangladesh percentile ranking powered by Neon PostgreSQL.

---

## 🏗️ Technology Stack

- **Frontend**: Responsive Single-Page Application (SPA), Tailwind CSS, KaTeX LaTeX renderer, Chart.js analytics, Touch-optimized for mobile.
- **Backend API**: Python 3.12 Serverless Handler (`http.server.BaseHTTPRequestHandler`) on Vercel.
- **Database**: Neon Serverless PostgreSQL with PgBouncer connection pooling.
- **Hosting & CDN**: Vercel Edge Serverless Platform.

---

## 🚀 Vercel Deployment Guide

1. Log in to [Vercel Dashboard](https://vercel.com/dashboard).
2. Click **"Add New..."** -> **"Project"**.
3. Select your GitHub repository: **`karim8siam/AdmissionTestBD-EV-`**.
4. Set Environment Variable:
   - **Name**: `DATABASE_URL`
   - **Value**:
     ```text
     postgresql://neondb_owner:npg_okZQmgr0e1fv@ep-frosty-grass-b5eq2vv9-pooler.c-7.us-east-2.aws.neon.tech/neondb?sslmode=require
     ```
5. Click **"Deploy"**. The site will be live within seconds!

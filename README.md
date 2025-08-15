# UIUC Class Seat Monitor Bot

A Python + Playwright bot that automatically checks the University of Illinois **Banner Self-Service** registration system for open seats in specific course sections and sends updates to a Discord channel.

Originally designed to monitor **ECE 210 — Analog Signal Processing (AL2)** for Fall 2025, but easily adaptable to any CRN/section.

---

## Features

- **Automates course search** on the registration page.
- **Navigates to the correct results page** (e.g., page 2 if your section is listed there).
- **Parses seat availability** (`X of Y seats`).
- **Randomized refresh interval** (default: 30 ± 5 seconds).
- **Discord integration** via Webhooks.
- **Notification throttling**:
  - Sends **once per hour** if section status is unchanged.
  - Sends **immediately** if seats open (no matter when).

---

## Requirements

- Python 3.9+
- [Playwright](https://playwright.dev/python/)
- Requests

---

## Installation

```bash
git clone https://github.com/yourusername/uiuc-seat-monitor.git
cd uiuc-seat-monitor

pip install -r requirements.txt
playwright install chromium

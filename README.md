# **LRT-2 Train Density & Reporting System**

An intelligent transport management system designed to monitor real-time passenger density, manage station queues, and generate analytical reports for the LRT-2 (Light Rail Transit) system in the Philippines.

## **📋 Project Overview**

Public transportation in Metro Manila, specifically the LRT-2, often faces severe overcrowding. This leads to commuter anxiety and inefficient fleet allocation.

This project addresses these issues by:

1. **For Commuters:** Providing real-time data on train capacity (Low, Medium, High) so passengers can decide whether to queue or wait.  
2. **For Administrators (DOTr):** collecting historical data to generate Daily and Weekly reports, identifying peak hours and overcrowded trains to improve future train allocation.

## **🚀 Key Features**

* **Real-Time Monitoring:** Tracks passenger counts and density levels for active trains.  
* **Station Queue Management:** Simulates trains arriving and departing stations using FIFO (First-In-First-Out) logic.  
* **Data Analytics:**  
  * **Daily Reports:** Identifies specific hours of high congestion.  
  * **Weekly Reports:** Ranks days of the week by average passenger density.  
* **Admin Dashboard:** A robust Django admin interface to manage Stations, Trains, and view Historical Logs.

## **🛠️ Tech Stack**

* **Backend:** Python 3, Django Framework  
* **Database:** SQLite (Default Django DB)  
* **Frontend:** HTML, CSS, JavaScript (for search/dropdowns)  
* **Tools:** Google Colab (Initial Simulation), Git

## **🧠 Algorithms & Data Structures**

This project demonstrates the practical application of various computer science concepts:

| Component | Algorithm / Structure | Complexity | Usage |
| :---- | :---- | :---- | :---- |
| **Real-Time DB** | **Hash Table** (Dictionary) | O(1) | Instant retrieval of a train's current passenger count. |
| **Station Queues** | **Linked List Queue** | O(1) | Managing the sequence of trains arriving at a station (Push/Pop). |
| **Daily Peak** | **Merge Sort** | O(N \\log N) | Efficiently sorting daily trains to find the single highest capacity train. |
| **Weekly Rank** | **Merge Sort** | O(N \\log N) | A stable sort used to rank the days of the week by average density for reports. |
| **Search** | **Linear Search** | O(N) | Searching for specific high-density timestamps or specific trains in a list. |

## **📂 Project Structure**

LRT2\_System/  
├── manage.py  
├── myapp/  
│   ├── models.py       \# Defines Station, Train, HistoricalRecord  
│   ├── views.py        \# Contains the Algorithm Logic (Merge/Heap Sort)  
│   ├── admin.py        \# Configuration for the DOTr Admin Panel  
│   ├── urls.py  
│   └── templates/  
│       └── ...  
└── README.md

## **⚙️ Installation & Setup**

1. **Clone the repository**  
   git clone \[https://github.com/yourusername/lrt2-density-system.git\](https://github.com/yourusername/lrt2-density-system.git)  
   cd lrt2-density-system

2. **Create a Virtual Environment (Optional but Recommended)**  
   python \-m venv venv  
   \# Windows  
   venv\\Scripts\\activate  
   \# Mac/Linux  
   source venv/bin/activate

3. Create an Admin Account  
   You need this to access the dashboard.  
   python manage.py createsuperuser

4. **Run the Server**  
   python manage.py runserver

## **📊 How to Use**

### **1\. Setting Up Data (Admin Panel)**

* Log in to the Admin Panel.  
* Go to **Stations** and add the LRT-2 stations (e.g., Santolan, Katipunan, Anonas).  
* Go to **Trains** and add active trains (e.g., T01, T02) with their max capacity.

### **2\. Simulating Traffic**

* You can use the provided Django Shell script or the views to simulate passengers boarding.  
* As trains update, HistoricalRecord entries are automatically created.

### **3\. Viewing Reports**

* Navigate to the **Historical Records** section in the Admin Panel.  
* **Filter by Day:** See data for specific days.  
* **Filter by Density:** Click "High" on the sidebar to perform a Linear Search for overcrowding events.
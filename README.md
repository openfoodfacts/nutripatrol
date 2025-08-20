# **NutriPatrol 🛡️**

**A collaborative tool to monitor and improve food product data on Open Food Facts.**

NutriPatrol is a web-based application designed to help the Open Food Facts community ensure the quality and accuracy of the data in the world's largest open database of food products. It allows users to easily patrol recent changes, spot inaccuracies, and contribute to making the food supply chain more transparent.

Production: <https://nutripatrol.openfoodfacts.org>
Pre-production: <https://nutripatrol.openfoodfacts.net>

## This is the backend
- The frontend is located at https://github.com/openfoodfacts/nutripatrol-frontend

## **🌟 About the Project**

The goal of NutriPatrol is to gamify the process of data verification for Open Food Facts. Moderators can quickly swipe through recent reports, to act on true issues and mark them as fixed, or flag incorrect ones as not a problem. This helps maintain the integrity of the data that powers countless apps and research projects related to food, nutrition, and health.

### **Key Features:**

* **🕵️‍♀️ Patrol Recent Reports:** Quickly review and verify edits made to products.  
* **✅ Approve or Flag from many places:** Basic integration is available in the website (openfoodfacts-server), being added to openfoodfacts-explorer and the mobile app (smooth-app)  
* **📱 Mobile-Friendly:** A responsive design that works on any device.

## **🚀 Getting Started**

To get a local copy up and running, follow these simple steps.

### **Prerequisites**

### **Installation**

1. Clone this repository :

```console
git clone https://github.com/openfoodfacts/nutripatrol.git
```

```console
cd nutripatrol
```

### Run with docker containers

Make docker containers

```console
make up
```

Your local instance of NutriPatrol should now be running at http://localhost:3000.
### Authentication for local dev

### To test with a global instance of Product Opener

In .env file uncomment the AUTH_SERVER_STATIC variable.
If you want to use a local Product Opener Instance, use `http://world.openfoodfacts.localhost`

Then connect to your Open Food Facts profile, copy the session cookie (use developper toolbar, and find a cookie named session for openfoodfacts.org domain, copy its value)
and paste it in the body at this endpoint /api/set_session_cookie (you have a form at the /api/docs URI).

## **📖 Usage**

Once the application is running, you can log in with your Open Food Facts account. The main screen will present you with cards showing recent reports. You might need to be a moderator to be able to use it.

### **How to Contribute**


## Pre-Commit

This repo uses [pre-commit](https://pre-commit.com/) to enforce code styling, etc. To use it:

```console
pre-commit run
```
## **🤝 Contributing**

Contributions are what make the open-source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this project better, please fork the repo and create a pull request. You can also simply open an issue with the type "enhancement".


## Wikipage

- <https://wiki.openfoodfacts.org/Moderation>
- [Meeting minutes](https://docs.google.com/document/d/1B9Ci42kl_jrFt2hi3PiWW9tM9l6B1sI5kQMI9Zd6QS4/edit)

## Meeting

Valentin (@valimp) and Raphael (@raphael0202) are working on this tool. They meet weekly. Please ping them on Slack if you'd like to contribute.
We have more general quality meetings every month.

Please read our [Contributing Guidelines](https://github.com/openfoodfacts/nutripatrol/blob/main/CONTRIBUTING.md) for more details on our code of conduct and the process for submitting pull requests.

## **📜 License**

Distributed under the AGPL. See LICENSE for more information.

## **📬 Contact**

Open Food Facts - tech@openfoodfacts.org

Project Link: [https://github.com/openfoodfacts/nutripatrol](https://github.com/openfoodfacts/nutripatrol)

This README is a starting point. Feel free to suggest improvements!


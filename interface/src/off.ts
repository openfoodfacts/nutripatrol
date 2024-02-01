const offService = {
  // Get cookie by name return empty string if not found
  getCookie(name: any) {
      const cookies = document.cookie
          .split(";")
          .filter((item) => item.trim().startsWith(`${name}=`));
      if (cookies.length) {
          const cookie = cookies[0];
          return cookie.split("=", 2)[1];
      }
      return "";
  },

  // Get user id from cookie return empty string if not found
  getUsername() {
    const sessionCookie = this.getCookie("session");

    if (!sessionCookie.length) {
      return "";
    }

    let isNext = false;
    let username = "";
    sessionCookie.split("&").forEach((el) => {
      if (el === "user_id") {
        isNext = true;
      } else if (isNext) {
        username = el;
        isNext = false;
      }
    });
    return username;
  },
};

export default offService;
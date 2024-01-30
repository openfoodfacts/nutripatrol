const offService = {
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

// Fetching products to annotate:

// https://world.openfoodfacts.org/cgi/search.pl?page=0&page_size=25&json=true&action=process&fields=code,lang,image_ingredients_url,product_name,ingredient,images&tagtype_0=states&tag_contains_0=contains&tag_0=en%3Aingredients-to-be-completed&tagtype_1=states&tag_contains_1=contains&tag_1=en%3Aingredients-photo-selected

// Getting prediction:
// https://robotoff.openfoodfacts.org/api/v1/predict/ingredient_list?ocr_url=https://images.openfoodfacts.org/images/products/505/382/713/9229/41.json
// https://images.openfoodfacts.org/images/products/505/382/713/9229/41.json
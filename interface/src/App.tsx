import {
  Route,
  Routes
} from "react-router-dom";
import { useState, useCallback, useRef, useEffect } from "react";
import off from "./off.ts";
import axios from "axios";

import HomePage from '../pages/HomePage.tsx'
import ModerationPage from '../pages/ModerationPage.tsx'
import LoginPage from '../pages/LoginPage.tsx'
import LayoutMenu from "../components/Layouts/LayoutMenu.tsx";
import LoginContext from "./context/login.tsx";

export default function App() {

  const [userState, setUserState] = useState(() => {
    return {
      userName: "",
      isLoggedIn: false,
    };
  });

  const lastSeenCookie = useRef<string | null>(null);

  const refresh = useCallback(async () => {
    // Get the session cookie
    const sessionCookie = off.getCookie("session");
    if (sessionCookie === lastSeenCookie.current) {
      return userState.isLoggedIn;
    }
    if (!sessionCookie) {
      setUserState({
        userName: "",
        isLoggedIn: false,
      });
      lastSeenCookie.current = sessionCookie;
      return false;
    }
    const isLoggedIn = axios
      .get("https://world.openfoodfacts.org/cgi/session.pl", {
        withCredentials: true,
      })
      .then(() => {
        const cookieUserName = off.getUsername();
        setUserState({
          userName: cookieUserName,
          isLoggedIn: true,
        })
        lastSeenCookie.current = sessionCookie;
        return true;
      })
      .catch(() => {
        setUserState({
          userName: "",
          isLoggedIn: false,
        })
        lastSeenCookie.current = sessionCookie;
        return false;
      });
      
    return isLoggedIn;
  }, [userState.isLoggedIn]);

  useEffect(() => {
    refresh(); 
  }, [refresh]);

  return (
      <LoginContext.Provider value={{ ...userState, refresh }}>
        <LayoutMenu>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/moderation" element={userState.isLoggedIn ? < ModerationPage/> : <LoginPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="*" element={<h1>Not Found</h1>} />
          </Routes>
        </LayoutMenu>
      </LoginContext.Provider>
    )
}
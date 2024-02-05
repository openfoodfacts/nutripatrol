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
import LoginContext from "./contexts/login.tsx";
import NotFound from "../pages/NotFound.tsx";

export default function App() {

  // turn in to true to test the moderation page - it will always be logged in
  const devMode = (import.meta.env.VITE_DEVELOPPEMENT_MODE === "development");
  

  const [userState, setUserState] = useState(() => {
    if (devMode) {
      return {
        userName: "",
        isLoggedIn: true,
      };
    }
    return {
      userName: "",
      isLoggedIn: false,
    };
  });
  

  const lastSeenCookie = useRef<string | null>(null);

  const refresh = useCallback(async () => {
    if (devMode) {
      setUserState({
        userName: "",
        isLoggedIn: true,
      });
    }
    // Get the session cookie
    const sessionCookie = off.getCookie("session");
    // If the session cookie is the same as the last seen cookie, return the current login state
    if (sessionCookie === lastSeenCookie.current) {
      return userState.isLoggedIn;
    }
    // If the session cookie is null, the user is not logged in
    if (!sessionCookie) {
      setUserState({
        userName: "",
        isLoggedIn: false,
      });
      lastSeenCookie.current = sessionCookie;
      return false;
    }
    // If the session cookie is not null, send a request to the server to check if the user is logged in
    const isLoggedIn = axios
      .get(`${import.meta.env.VITE_PO_URL}/cgi/session.pl`, {
        withCredentials: true,
      })
      // If the request is successful, set the user state to logged in
      .then(() => {
        const cookieUserName = off.getUsername();
        setUserState({
          userName: cookieUserName,
          isLoggedIn: true,
        })
        lastSeenCookie.current = sessionCookie;
        return true;
      })
      // If the request is not successful, set the user state to logged out
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
              <Route path="*" element={<NotFound />} />
            </Routes>
          </LayoutMenu>
      </LoginContext.Provider>
    )
}
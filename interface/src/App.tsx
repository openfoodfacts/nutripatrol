import {
  Route,
  Routes
} from "react-router-dom";

import HomePage from '../pages/HomePage.tsx'
import ModerationPage from '../pages/ModerationPage.tsx'
import LoginPage from '../pages/LoginPage.tsx'
import LayoutMenu from "../components/Layouts/LayoutMenu.tsx";

export default function App() {
    return (
        <LayoutMenu>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/moderation" element={< ModerationPage/>} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="*" element={<h1>Not Found</h1>} />
          </Routes>
        </LayoutMenu>
    )
}
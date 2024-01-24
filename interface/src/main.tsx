import ReactDOM from 'react-dom/client'
import {
  BrowserRouter as Router,
  Route,
  Routes
} from "react-router-dom";
import App from './App.tsx'
import ModerationPage from '../pages/ModerationPage.tsx'
import LoginPage from '../pages/LoginPage.tsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <Router>
    <Routes>
      <Route path="/" element={<App />} />
      <Route path="/moderation" element={< ModerationPage/>} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="*" element={<h1>Not Found</h1>} />
    </Routes>
  </Router>,
)

import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import './styles/main.css'

const router = createRouter({
    history: createWebHistory(),
    routes: [
        {
            path: '/',
            name: 'home',
            component: () => import('./views/Home.vue')
        },
        {
            path: '/search',
            name: 'search',
            component: () => import('./views/Search.vue')
        },
        {
            path: '/entry/:id',
            name: 'entry',
            component: () => import('./views/EntryDetail.vue')
        },
        {
            path: '/collections',
            name: 'collections',
            component: () => import('./views/Collections.vue')
        },
        {
            path: '/admin',
            name: 'admin',
            component: () => import('./views/Admin.vue')
        },
        {
            path: '/browse',
            name: 'browse',
            component: () => import('./views/Browse.vue')
        }
    ]
})

const app = createApp(App)
app.use(router)
app.mount('#app')

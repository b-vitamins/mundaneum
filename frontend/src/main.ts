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
        },
        {
            path: '/authors',
            name: 'authors',
            component: () => import('./views/Authors.vue')
        },
        {
            path: '/authors/:id',
            name: 'author-detail',
            component: () => import('./views/AuthorDetail.vue')
        },
        {
            path: '/venues',
            name: 'venues',
            component: () => import('./views/Venues.vue')
        },
        {
            path: '/venues/:slug',
            name: 'venue-detail',
            component: () => import('./views/VenueDetail.vue')
        },
        {
            path: '/subjects',
            name: 'subjects',
            component: () => import('./views/Subjects.vue')
        },
        {
            path: '/subjects/:slug',
            name: 'subject-detail',
            component: () => import('./views/SubjectDetail.vue')
        },
        {
            path: '/topics',
            name: 'topics',
            component: () => import('./views/Topics.vue')
        },
        {
            path: '/topics/:slug',
            name: 'topic-detail',
            component: () => import('./views/TopicDetail.vue')
        }
    ]
})

const app = createApp(App)
app.use(router)
app.mount('#app')

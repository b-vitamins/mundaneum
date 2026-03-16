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
            path: '/entry/:id/graph',
            name: 'graph',
            component: () => import('./views/GraphExplorer.vue')
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
            component: () => import('./views/CatalogListPage.vue'),
            props: { entity: 'authors' }
        },
        {
            path: '/authors/:id',
            name: 'author-detail',
            component: () => import('./views/CatalogDetailPage.vue'),
            props: { entity: 'authors' }
        },
        {
            path: '/venues',
            name: 'venues',
            component: () => import('./views/CatalogListPage.vue'),
            props: { entity: 'venues' }
        },
        {
            path: '/venues/:slug',
            name: 'venue-detail',
            component: () => import('./views/CatalogDetailPage.vue'),
            props: { entity: 'venues' }
        },
        {
            path: '/subjects',
            name: 'subjects',
            component: () => import('./views/CatalogListPage.vue'),
            props: { entity: 'subjects' }
        },
        {
            path: '/subjects/:slug',
            name: 'subject-detail',
            component: () => import('./views/CatalogDetailPage.vue'),
            props: { entity: 'subjects' }
        },
        {
            path: '/topics',
            name: 'topics',
            component: () => import('./views/CatalogListPage.vue'),
            props: { entity: 'topics' }
        },
        {
            path: '/topics/:slug',
            name: 'topic-detail',
            component: () => import('./views/CatalogDetailPage.vue'),
            props: { entity: 'topics' }
        },
        {
            path: '/trends',
            name: 'trends',
            component: () => import('./views/Trends.vue')
        },
        {
            path: '/concepts',
            name: 'concepts',
            component: () => import('./views/ConceptBundles.vue')
        },
        {
            path: '/concepts/:index',
            name: 'concept-detail',
            component: () => import('./views/BundleDetail.vue')
        },
        {
            path: '/entities',
            name: 'entities',
            component: () => import('./views/NerEntityList.vue')
        },
        {
            path: '/entities/:id',
            name: 'entity-detail',
            component: () => import('./views/NerEntityDetail.vue')
        },
        {
            path: '/:pathMatch(.*)*',
            name: 'not-found',
            component: () => import('./views/NotFound.vue')
        }
    ]
})

const app = createApp(App)
app.use(router)
app.mount('#app')

--
-- PostgreSQL database dump
--

-- Dumped from database version 17.5
-- Dumped by pg_dump version 17.5

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: products; Type: TABLE; Schema: public; Owner: automation_admin
--

CREATE TABLE public.products (
    sku character varying(100) NOT NULL,
    name character varying(500) NOT NULL,
    description text,
    category_id integer,
    category_name character varying(255),
    is_active boolean DEFAULT true NOT NULL,
    list_price numeric(15,2) DEFAULT 0,
    standard_price numeric(15,2) DEFAULT 0,
    product_type character varying(50),
    barcode character varying(100),
    weight numeric(10,3) DEFAULT 0,
    volume numeric(10,3) DEFAULT 0,
    sale_ok boolean DEFAULT true,
    purchase_ok boolean DEFAULT true,
    uom_id integer,
    uom_name character varying(100),
    company_id integer,
    text_for_embedding text,
    embedding public.vector(1536),
    last_update timestamp with time zone,
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.products OWNER TO automation_admin;

--
-- Data for Name: products; Type: TABLE DATA; Schema: public; Owner: automation_admin
--

COPY public.products (sku, name, description, category_id, category_name, is_active, list_price, standard_price, product_type, barcode, weight, volume, sale_ok, purchase_ok, uom_id, uom_name, company_id, text_for_embedding, embedding, last_update, created_at, updated_at) FROM stdin;
\.


--
-- Name: products products_pkey; Type: CONSTRAINT; Schema: public; Owner: automation_admin
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_pkey PRIMARY KEY (sku);


--
-- Name: idx_products_active; Type: INDEX; Schema: public; Owner: automation_admin
--

CREATE INDEX idx_products_active ON public.products USING btree (is_active);


--
-- Name: idx_products_category; Type: INDEX; Schema: public; Owner: automation_admin
--

CREATE INDEX idx_products_category ON public.products USING btree (category_id);


--
-- Name: idx_products_embedding; Type: INDEX; Schema: public; Owner: automation_admin
--

CREATE INDEX idx_products_embedding ON public.products USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: idx_products_last_update; Type: INDEX; Schema: public; Owner: automation_admin
--

CREATE INDEX idx_products_last_update ON public.products USING btree (last_update);


--
-- Name: idx_products_type; Type: INDEX; Schema: public; Owner: automation_admin
--

CREATE INDEX idx_products_type ON public.products USING btree (product_type);


--
-- Name: products update_products_updated_at; Type: TRIGGER; Schema: public; Owner: automation_admin
--

CREATE TRIGGER update_products_updated_at BEFORE UPDATE ON public.products FOR EACH ROW EXECUTE FUNCTION public.update_updated_at_column();


--
-- PostgreSQL database dump complete
--


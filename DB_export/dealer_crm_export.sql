--
-- PostgreSQL database dump
--

\restrict VEbWeIkXQ1quNmGLK6VjOw1U6UDF76t4YDCxIgCZ9Wa5VBKqnbp1JuaCFDiSpQg

-- Dumped from database version 16.14 (Debian 16.14-1.pgdg13+1)
-- Dumped by pg_dump version 16.14 (Debian 16.14-1.pgdg13+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
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
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: crm_app
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO crm_app;

--
-- Name: app_settings; Type: TABLE; Schema: public; Owner: crm_app
--

CREATE TABLE public.app_settings (
    key character varying(50) NOT NULL,
    value text NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.app_settings OWNER TO crm_app;

--
-- Name: customer_car; Type: TABLE; Schema: public; Owner: crm_app
--

CREATE TABLE public.customer_car (
    id integer NOT NULL,
    customer_id integer NOT NULL,
    make character varying(60),
    model character varying(60),
    year integer,
    ownership_type character varying(10),
    lease_end_date date,
    is_primary boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.customer_car OWNER TO crm_app;

--
-- Name: customer_car_id_seq; Type: SEQUENCE; Schema: public; Owner: crm_app
--

CREATE SEQUENCE public.customer_car_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.customer_car_id_seq OWNER TO crm_app;

--
-- Name: customer_car_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: crm_app
--

ALTER SEQUENCE public.customer_car_id_seq OWNED BY public.customer_car.id;


--
-- Name: customers; Type: TABLE; Schema: public; Owner: crm_app
--

CREATE TABLE public.customers (
    id integer NOT NULL,
    assigned_sales_id integer NOT NULL,
    full_name character varying(150) NOT NULL,
    email character varying(254),
    phone character varying(30),
    note character varying(2000),
    last_contacted_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.customers OWNER TO crm_app;

--
-- Name: customers_id_seq; Type: SEQUENCE; Schema: public; Owner: crm_app
--

CREATE SEQUENCE public.customers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.customers_id_seq OWNER TO crm_app;

--
-- Name: customers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: crm_app
--

ALTER SEQUENCE public.customers_id_seq OWNED BY public.customers.id;


--
-- Name: email_drafts; Type: TABLE; Schema: public; Owner: crm_app
--

CREATE TABLE public.email_drafts (
    id integer NOT NULL,
    sales_id integer NOT NULL,
    customer_id integer NOT NULL,
    rule_id integer,
    subject character varying(300) NOT NULL,
    body text NOT NULL,
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    approved_at timestamp with time zone
);


ALTER TABLE public.email_drafts OWNER TO crm_app;

--
-- Name: email_drafts_id_seq; Type: SEQUENCE; Schema: public; Owner: crm_app
--

CREATE SEQUENCE public.email_drafts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.email_drafts_id_seq OWNER TO crm_app;

--
-- Name: email_drafts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: crm_app
--

ALTER SEQUENCE public.email_drafts_id_seq OWNED BY public.email_drafts.id;


--
-- Name: interactions; Type: TABLE; Schema: public; Owner: crm_app
--

CREATE TABLE public.interactions (
    id integer NOT NULL,
    customer_id integer NOT NULL,
    sales_id integer NOT NULL,
    channel character varying(20) NOT NULL,
    summary character varying(2000) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    contacted_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.interactions OWNER TO crm_app;

--
-- Name: interactions_id_seq; Type: SEQUENCE; Schema: public; Owner: crm_app
--

CREATE SEQUENCE public.interactions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.interactions_id_seq OWNER TO crm_app;

--
-- Name: interactions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: crm_app
--

ALTER SEQUENCE public.interactions_id_seq OWNED BY public.interactions.id;


--
-- Name: inventory; Type: TABLE; Schema: public; Owner: crm_app
--

CREATE TABLE public.inventory (
    id integer NOT NULL,
    make character varying(60) NOT NULL,
    model character varying(60) NOT NULL,
    year integer NOT NULL,
    "trim" character varying(60),
    mileage integer,
    price numeric(12,2),
    vin character varying(17),
    status character varying(20) DEFAULT 'available'::character varying NOT NULL,
    added_at timestamp with time zone DEFAULT now() NOT NULL,
    features text,
    notes text
);


ALTER TABLE public.inventory OWNER TO crm_app;

--
-- Name: inventory_id_seq; Type: SEQUENCE; Schema: public; Owner: crm_app
--

CREATE SEQUENCE public.inventory_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.inventory_id_seq OWNER TO crm_app;

--
-- Name: inventory_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: crm_app
--

ALTER SEQUENCE public.inventory_id_seq OWNED BY public.inventory.id;


--
-- Name: llm_request_logs; Type: TABLE; Schema: public; Owner: crm_app
--

CREATE TABLE public.llm_request_logs (
    id integer NOT NULL,
    url character varying(500) NOT NULL,
    model character varying(200) NOT NULL,
    input json NOT NULL,
    output json NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.llm_request_logs OWNER TO crm_app;

--
-- Name: llm_request_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: crm_app
--

CREATE SEQUENCE public.llm_request_logs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.llm_request_logs_id_seq OWNER TO crm_app;

--
-- Name: llm_request_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: crm_app
--

ALTER SEQUENCE public.llm_request_logs_id_seq OWNED BY public.llm_request_logs.id;


--
-- Name: outreach_rules; Type: TABLE; Schema: public; Owner: crm_app
--

CREATE TABLE public.outreach_rules (
    id integer NOT NULL,
    sales_id integer NOT NULL,
    name character varying(150) NOT NULL,
    rule_text text NOT NULL,
    compiled_filter json,
    cadence_days integer,
    active boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    email_type character varying(30) DEFAULT 'lease_finance_ending'::character varying NOT NULL,
    custom_template text
);


ALTER TABLE public.outreach_rules OWNER TO crm_app;

--
-- Name: outreach_rules_id_seq; Type: SEQUENCE; Schema: public; Owner: crm_app
--

CREATE SEQUENCE public.outreach_rules_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.outreach_rules_id_seq OWNER TO crm_app;

--
-- Name: outreach_rules_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: crm_app
--

ALTER SEQUENCE public.outreach_rules_id_seq OWNED BY public.outreach_rules.id;


--
-- Name: sample_messages; Type: TABLE; Schema: public; Owner: crm_app
--

CREATE TABLE public.sample_messages (
    id integer NOT NULL,
    sales_id integer NOT NULL,
    channel character varying(10) NOT NULL,
    raw_content text NOT NULL,
    label character varying(100) DEFAULT ''::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.sample_messages OWNER TO crm_app;

--
-- Name: sample_messages_id_seq; Type: SEQUENCE; Schema: public; Owner: crm_app
--

CREATE SEQUENCE public.sample_messages_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sample_messages_id_seq OWNER TO crm_app;

--
-- Name: sample_messages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: crm_app
--

ALTER SEQUENCE public.sample_messages_id_seq OWNED BY public.sample_messages.id;


--
-- Name: style_categories; Type: TABLE; Schema: public; Owner: crm_app
--

CREATE TABLE public.style_categories (
    id integer NOT NULL,
    sales_id integer NOT NULL,
    channel character varying(10) NOT NULL,
    name character varying(100) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.style_categories OWNER TO crm_app;

--
-- Name: style_categories_id_seq; Type: SEQUENCE; Schema: public; Owner: crm_app
--

CREATE SEQUENCE public.style_categories_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.style_categories_id_seq OWNER TO crm_app;

--
-- Name: style_categories_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: crm_app
--

ALTER SEQUENCE public.style_categories_id_seq OWNED BY public.style_categories.id;


--
-- Name: style_profiles; Type: TABLE; Schema: public; Owner: crm_app
--

CREATE TABLE public.style_profiles (
    id integer NOT NULL,
    sales_id integer NOT NULL,
    channel character varying(10) NOT NULL,
    style_md text DEFAULT ''::text NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.style_profiles OWNER TO crm_app;

--
-- Name: style_profiles_id_seq; Type: SEQUENCE; Schema: public; Owner: crm_app
--

CREATE SEQUENCE public.style_profiles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.style_profiles_id_seq OWNER TO crm_app;

--
-- Name: style_profiles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: crm_app
--

ALTER SEQUENCE public.style_profiles_id_seq OWNED BY public.style_profiles.id;


--
-- Name: user_settings; Type: TABLE; Schema: public; Owner: crm_app
--

CREATE TABLE public.user_settings (
    user_id integer NOT NULL,
    key character varying(50) NOT NULL,
    value text NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.user_settings OWNER TO crm_app;

--
-- Name: users; Type: TABLE; Schema: public; Owner: crm_app
--

CREATE TABLE public.users (
    id integer NOT NULL,
    email character varying(254) NOT NULL,
    password_hash character varying(255) NOT NULL,
    name character varying(100) NOT NULL,
    role character varying(20) NOT NULL,
    must_change_password boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.users OWNER TO crm_app;

--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: crm_app
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.users_id_seq OWNER TO crm_app;

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: crm_app
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: customer_car id; Type: DEFAULT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.customer_car ALTER COLUMN id SET DEFAULT nextval('public.customer_car_id_seq'::regclass);


--
-- Name: customers id; Type: DEFAULT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.customers ALTER COLUMN id SET DEFAULT nextval('public.customers_id_seq'::regclass);


--
-- Name: email_drafts id; Type: DEFAULT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.email_drafts ALTER COLUMN id SET DEFAULT nextval('public.email_drafts_id_seq'::regclass);


--
-- Name: interactions id; Type: DEFAULT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.interactions ALTER COLUMN id SET DEFAULT nextval('public.interactions_id_seq'::regclass);


--
-- Name: inventory id; Type: DEFAULT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.inventory ALTER COLUMN id SET DEFAULT nextval('public.inventory_id_seq'::regclass);


--
-- Name: llm_request_logs id; Type: DEFAULT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.llm_request_logs ALTER COLUMN id SET DEFAULT nextval('public.llm_request_logs_id_seq'::regclass);


--
-- Name: outreach_rules id; Type: DEFAULT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.outreach_rules ALTER COLUMN id SET DEFAULT nextval('public.outreach_rules_id_seq'::regclass);


--
-- Name: sample_messages id; Type: DEFAULT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.sample_messages ALTER COLUMN id SET DEFAULT nextval('public.sample_messages_id_seq'::regclass);


--
-- Name: style_categories id; Type: DEFAULT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.style_categories ALTER COLUMN id SET DEFAULT nextval('public.style_categories_id_seq'::regclass);


--
-- Name: style_profiles id; Type: DEFAULT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.style_profiles ALTER COLUMN id SET DEFAULT nextval('public.style_profiles_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: crm_app
--

COPY public.alembic_version (version_num) FROM stdin;
0009
\.


--
-- Data for Name: app_settings; Type: TABLE DATA; Schema: public; Owner: crm_app
--

COPY public.app_settings (key, value, updated_at) FROM stdin;
\.


--
-- Data for Name: customer_car; Type: TABLE DATA; Schema: public; Owner: crm_app
--

COPY public.customer_car (id, customer_id, make, model, year, ownership_type, lease_end_date, is_primary, created_at, updated_at) FROM stdin;
1	1	Honda	Civic	2018	own	\N	t	2026-06-06 23:17:33.742031+00	2026-06-06 23:17:33.742031+00
2	2	Toyota	Corolla	2019	own	\N	t	2026-06-06 23:17:33.742031+00	2026-06-06 23:17:33.742031+00
3	3	Ford	F-150	2017	own	\N	t	2026-06-06 23:17:33.742031+00	2026-06-06 23:17:33.742031+00
5	5	Subaru	Outback	2016	own	\N	t	2026-06-06 23:17:33.742031+00	2026-06-06 23:17:33.742031+00
6	6	Mazda	CX-5	2022	finance	\N	t	2026-06-06 23:17:33.742031+00	2026-06-06 23:17:33.742031+00
7	7	Toyota	RAV4	2023	own	\N	t	2026-06-06 23:17:33.742031+00	2026-06-06 23:17:33.742031+00
8	8	Honda	CR-V	2021	finance	\N	t	2026-06-06 23:17:33.742031+00	2026-06-06 23:17:33.742031+00
9	11	Honda	Civic	2021	own	\N	t	2026-06-06 23:38:05.769054+00	2026-06-06 23:38:05.769054+00
4	4	Hyundai	Tucson	2020	lease	2026-06-30	t	2026-06-06 23:17:33.742031+00	2026-06-08 12:57:07.660993+00
\.


--
-- Data for Name: customers; Type: TABLE DATA; Schema: public; Owner: crm_app
--

COPY public.customers (id, assigned_sales_id, full_name, email, phone, note, last_contacted_at, created_at, updated_at) FROM stdin;
1	1	James Whitfield	james.whitfield@gmail.com	604-555-0101	Owns a used 2018 Honda Civic, considering upgrade.	2026-06-03 23:17:23.941388+00	2026-06-06 23:17:23.941388+00	2026-06-06 23:17:23.941388+00
2	1	Maria Santos	maria.santos@outlook.com	604-555-0102	Owns a used 2019 Toyota Corolla, looking at SUVs.	2026-06-01 23:17:23.941388+00	2026-06-06 23:17:23.941388+00	2026-06-06 23:17:23.941388+00
3	1	Derek Nguyen	derek.nguyen@gmail.com	778-555-0103	Owns a used 2017 Ford F-150, wants a newer truck.	2026-06-05 23:17:23.941388+00	2026-06-06 23:17:23.941388+00	2026-06-06 23:17:23.941388+00
5	1	Tom Kowalski	tom.kowalski@gmail.com	778-555-0105	Owns a used 2016 Subaru Outback, interested in EV.	2026-06-04 23:17:23.941388+00	2026-06-06 23:17:23.941388+00	2026-06-06 23:17:23.941388+00
6	1	Rachel Kim	rachel.kim@gmail.com	604-555-0106	Purchased 2022 Mazda CX-5 from us (financed). Happy buyer.	2026-05-27 23:17:23.941388+00	2026-06-06 23:17:23.941388+00	2026-06-06 23:17:23.941388+00
7	1	Carlos Mendez	carlos.mendez@yahoo.com	604-555-0107	Purchased 2023 Toyota RAV4 from us (cash). Repeat customer.	2026-05-23 23:17:23.941388+00	2026-06-06 23:17:23.941388+00	2026-06-06 23:17:23.941388+00
8	1	Stephanie Lau	stephanie.lau@gmail.com	778-555-0108	Purchased 2021 Honda CR-V from us (financed). Due for service.	2026-05-17 23:17:23.941388+00	2026-06-06 23:17:23.941388+00	2026-06-06 23:17:23.941388+00
9	1	Nathan Osei	nathan.osei@gmail.com	604-555-0109	No vehicle. Browsing inventory, interested in sedans.	2026-06-02 23:17:23.941388+00	2026-06-06 23:17:23.941388+00	2026-06-06 23:17:23.941388+00
10	1	Aisha Tremblay	aisha.tremblay@outlook.com	778-555-0110	No vehicle. First-time buyer, watching for deals under 30k.	2026-05-31 23:17:23.941388+00	2026-06-06 23:17:23.941388+00	2026-06-06 23:17:23.941388+00
11	1	sarah lee	sarah.lee@sample.com	\N	\N	\N	2026-06-06 23:38:05.769054+00	2026-06-08 12:22:26.867396+00
4	1	Priya Sharma	priya.sharma@hotmail.com	604-555-0104	leased a 2020 Hyundai Tucson, new immigrant family with 2 kids. commit with work 30 mins everyday\n happy but open to lease.	2026-06-10 19:04:55.760731+00	2026-06-06 23:17:23.941388+00	2026-06-10 19:04:55.758669+00
\.


--
-- Data for Name: email_drafts; Type: TABLE DATA; Schema: public; Owner: crm_app
--

COPY public.email_drafts (id, sales_id, customer_id, rule_id, subject, body, status, created_at, approved_at) FROM stdin;
1	1	4	3	<think>**Crafting a professional email**	I need to compose an email in a precise JSON format, keeping the body under 150 words and professional. I should naturally mention that the lease ends on June 30, 2026, and express happiness while being open to leasing. I’m considering referencing 1-2 car options, like the Tiguan and the Jetta, keeping in mind that she owns a Tucson, making the Tiguan relevant. It would also be good to mention the Jetta if she’s interested in something more compact. I’ll need to ensure that I escape newlines properly for the JSON format.</think>\n\n{"subject":"Priya, a couple of options to consider before your Tucson lease ends","body":"Hi Priya,\\n\\nI hope you’re doing well. I see your 2020 Hyundai Tucson lease runs through June 30, 2026, and since you’ve been happy with it but are open to leasing again, I wanted to share a couple of options that may be worth considering.\\n\\nIf you’d like to stay with a similar SUV feel, the 2025 Volkswagen Tiguan S at $29,495 is a great fit. If you’re open to something more compact and budget-friendly, the 2025 Volkswagen Jetta S at $21,990 is also a strong option.\\n\\nIf either stands out, I’d be happy to send more details or set up a time for you to take a look.\\n\\nBest regards,"}	dismissed	2026-06-08 13:20:49.865208+00	\N
2	1	4	3	Priya, options to consider for your Tucson lease	Hi Priya,\n\nI wanted to reach out regarding your 2020 Hyundai Tucson lease, which ends on June 30, 2026. Since you mentioned you’re happy with the Tucson but open to leasing again, I thought I’d share a couple of options that may be a good fit.\n\nIf you’d like to stay with a similar SUV, the 2025 Volkswagen Tiguan S at $29,495 offers updated features and a comfortable, practical ride. If you’re open to something more budget-friendly, the 2025 Volkswagen Jetta S at $21,990 is also a great value.\n\nIf either one interests you, I’d be happy to send more details or put together some lease options.\n\nBest regards,	dismissed	2026-06-08 13:23:56.887372+00	\N
3	1	4	3	Priya, a smooth option to explore before your Tucson lease ends	Hi Priya,\n\nI hope you are doing well. Since you have been enjoying your 2020 Hyundai Tucson and are open to leasing again, I just wanted to reach out as your lease approaches its June 2026 end date.\n\nIf you would like to start comparing options early, the 2025 Volkswagen Tiguan S could be a very comfortable next step, with updated technology, safety features, and the versatility many Tucson drivers appreciate. If a smaller vehicle is also of interest, the 2025 Volkswagen Golf Base is another practical option to review.\n\nI would be happy to help you compare payments and timing whenever it feels convenient. Please let me know if you have any questions.\n\nBest regards,\nSales Team	dismissed	2026-06-08 13:47:17.576932+00	\N
4	1	4	3	A couple of options to consider for your 2020 Hyundai Tucson	Hi Priya,\n\nI hope you are doing well. Since you have been happy with your 2020 Hyundai Tucson and are open to leasing again, I just wanted to reach out with a couple of options that may be worth a look as your lease approaches its June 30, 2026 end date.\n\nIf you would like to stay with a comfortable SUV, the 2025 Volkswagen Tiguan S is a great fit with updated technology and safety features. If you are also open to something more payment-friendly, the 2025 Volkswagen Jetta S could be a very good value.\n\nI would be happy to help you review and compare both whenever it is convenient for you. Please let me know if you have any questions.\n\nBest regards,	dismissed	2026-06-08 13:55:07.613762+00	\N
5	1	4	3	Priya, planning ahead for your 2020 Hyundai Tucson lease	Hi Priya,\n\nI hope you and your family are doing well. I wanted to reach out early regarding your 2020 Hyundai Tucson lease ending on June 30, 2026, so the next steps can feel smooth and seamless with no pressure.\n\nWith two kids and your daily 30-minute commute, a couple of options may be worth keeping in mind:\n1. 2025 Volkswagen Tiguan S - a practical step up in space for family life.\n2. 2025 Volkswagen Jetta S - a comfortable, efficient choice if keeping commuting costs in check is the priority.\n\nYou may be perfectly happy in the Tucson for now, and I completely understand. When the time is right, we are here to help review lease options and make the process easy.\n\nThank you, Priya. I look forward to helping whenever you're ready.\n\nWarm regards,	dismissed	2026-06-08 14:02:03.056696+00	\N
6	1	4	3	Planning ahead for your 2020 Hyundai Tucson lease	Hi Priya,\n\nI hope you and your family are doing well.\n\nI wanted to reach out about your 2020 Hyundai Tucson lease, which matures on June 30, 2026. There is still time, and I am happy to help make the process simple and easy to navigate.\n\nYour options are straightforward.\n\n1. If you would like to stay in a family-friendly SUV, the 2025 Volkswagen Tiguan S could be a nice fit for two kids and everyday comfort.\n\n2. If a practical commuter with strong value is more appealing, the 2025 Volkswagen Jetta S is also worth considering for your 30-minute daily drive.\n\nYou can also keep your current vehicle or simply return it when the time comes.\n\nIf you would like, we can review the numbers together and see what feels like the best fit.	dismissed	2026-06-08 14:09:39.021344+00	\N
7	1	4	3	Your 2020 Hyundai Tucson lease options for June 2026	Hi Priya,\n\nI hope you and your family are doing well.\n\nI am reaching out regarding your 2020 Hyundai Tucson lease, which is set to mature on June 30, 2026. I know that may still feel a little ways off, but starting the conversation early can make the process much more smooth and easy to navigate.\n\nIf your Tucson has been serving you well for your daily commute and family needs, that is great. My role is simply to help you review your options and make sure the next step feels simple and comfortable when the time comes.\n\nOptions to consider:\n\n1. You can keep your current vehicle and review a lease-end buyout if that feels like the best fit.\n\n2. You can return your vehicle and explore something new on lease, especially if you would like updated features, warranty coverage, or a better fit for your family.\n\nFor example, the 2025 Volkswagen Tiguan S could be a nice option if you want to stay with a practical SUV for two kids and everyday driving. If a more budget-conscious commuter is worth considering, the 2025 Volkswagen Jetta S is another strong option.\n\nNext step:\n\nWhenever it is convenient, I would be happy to go over numbers, timing, and the different paths available so everything feels clear and seamless.\n\nThank you again for your relationship with the dealership, Priya. Please feel free to reply to this email or call me anytime if I can help.\n\nKind regards,\nAlex Morgan\nSales Representative	pending	2026-06-08 14:13:32.485463+00	\N
8	1	4	3	Priya, planning ahead for your 2020 Hyundai Tucson lease	Hi Priya,\n\nI hope you and your family are doing well.\n\nIt is hard to believe how quickly time passes, and I wanted to reach out regarding your 2020 Hyundai Tucson lease, which is set to mature on June 30, 2026.\n\nThe good news is there is still plenty of time to review your options and make the next step feel smooth and convenient around your work schedule.\n\nYour Options\n\n1. You can lease again and move into something newer with updated features and a fresh warranty.\n\n2. You can review a purchase option if you would prefer to keep your current Tucson.\n\n3. You can upgrade to something that may suit your family’s needs a little differently as things change.\n\nFor example, the 2025 Volkswagen Tiguan S could be a great fit if you would like to stay with a practical SUV for two growing kids and everyday driving. If you are also open to something more commuter-friendly, the 2025 Volkswagen Jetta S is an excellent value and easy on daily driving.\n\nNext Steps\n\nIf you would like, I can help you compare payments, review lease-end timing, and outline what each option would look like so everything is clear and easy.\n\nWe can do this by reply, over the phone, or during a quick visit at a time that works for you.\n\nThank you again for your continued relationship with us, Priya. I appreciate the opportunity to assist and make this transition as simple as possible.\n\nWarm regards,\n[Your Name]\nSales Representative	approved	2026-06-10 18:50:43.31181+00	2026-06-10 19:04:55.760731+00
\.


--
-- Data for Name: interactions; Type: TABLE DATA; Schema: public; Owner: crm_app
--

COPY public.interactions (id, customer_id, sales_id, channel, summary, created_at, contacted_at) FROM stdin;
1	1	1	call	Called James to discuss his lease renewal options for next spring. He is interested in the new RAV4 hybrid lineup.	2026-06-07 00:41:10.764323+00	2026-05-28 10:15:00+00
2	1	1	email	Sent James a comparison sheet for RAV4 Hybrid vs Highlander Hybrid. He replied asking about financing terms.	2026-06-07 00:41:10.764323+00	2026-06-01 09:00:00+00
3	2	1	in-person	Maria came in for a test drive on the 2025 Camry SE. Very positive — wants to bring her husband next visit before deciding.	2026-06-07 00:41:10.764323+00	2026-05-30 14:30:00+00
4	3	1	text	Texted Derek a reminder about his scheduled service appointment on Friday. He confirmed he will be there.	2026-06-07 00:41:10.764323+00	2026-06-03 11:45:00+00
6	5	1	email	Sent Tom a follow-up on the trade-in appraisal for his 2019 F-150. Estimated value 4,500. He is considering it.	2026-06-07 00:41:10.764323+00	2026-05-27 08:30:00+00
7	5	1	call	Tom called back to negotiate on the trade-in value. We agreed on 5,000. He will finalize paperwork next week.	2026-06-07 00:41:10.764323+00	2026-06-04 13:00:00+00
8	6	1	text	Rachel texted asking if the white Corolla she liked is still available. Confirmed it is and sent her the window sticker link.	2026-06-07 00:41:10.764323+00	2026-06-05 09:20:00+00
9	7	1	in-person	Carlos came in to pick up his new Civic. Walked through all the features and set up his phone pairing. Very happy with the purchase.	2026-06-07 00:41:10.764323+00	2026-05-20 11:00:00+00
10	8	1	call	Called Stephanie to check in after her recent purchase. She loves the Mazda CX-5 and asked about all-season tire options.	2026-06-07 00:41:10.764323+00	2026-06-03 15:00:00+00
11	9	1	email	Emailed Nathan about an upcoming EV incentive event. He has been watching the market — asked to be on the invite list.	2026-06-07 00:41:10.764323+00	2026-05-29 10:00:00+00
12	10	1	call	Aisha called to ask about leasing a vehicle for her small business. Explained fleet pricing and she is reviewing the brochures sent.	2026-06-07 00:41:10.764323+00	2026-06-02 09:45:00+00
13	11	1	text	Texted Sarah a reminder that her deposit hold expires in 3 days. She confirmed she wants to proceed with the purchase.	2026-06-07 00:41:10.764323+00	2026-06-05 14:10:00+00
14	4	1	email	Outreach email approved: Priya, planning ahead for your 2020 Hyundai Tucson lease	2026-06-10 19:04:55.758669+00	2026-06-10 19:04:55.760731+00
\.


--
-- Data for Name: inventory; Type: TABLE DATA; Schema: public; Owner: crm_app
--

COPY public.inventory (id, make, model, year, "trim", mileage, price, vin, status, added_at, features, notes) FROM stdin;
1	Volkswagen	Jetta	2025	S	0	21990.00	1VWFE7A35PC000001	available	2026-05-09 12:17:51.052602+00	\N	\N
2	Volkswagen	Golf	2025	Base	0	25990.00	1VWBC7AJXPC000002	available	2026-05-12 12:17:51.053768+00	\N	\N
3	Volkswagen	Tiguan	2025	S	0	29495.00	1V2WR2CA3PC000003	available	2026-05-15 12:17:51.053825+00	\N	\N
4	Volkswagen	Atlas	2025	S	0	36995.00	1V2LR2CA5PC000004	available	2026-05-18 12:17:51.05385+00	\N	\N
5	Volkswagen	GTI	2025	S	0	32895.00	1VWGF7A34PC000005	available	2026-05-21 12:17:51.053868+00	\N	\N
6	Volkswagen	Taos	2025	S	0	24995.00	1V2WR2CA7PC000006	available	2026-05-24 12:17:51.053888+00	\N	\N
7	Volkswagen	ID.4	2025	Standard	0	38995.00	1V2WRPE85PC000007	available	2026-05-27 12:17:51.053904+00	\N	\N
8	Volkswagen	Atlas Cross Sport	2025	SE	0	42995.00	1V2LR2CA9PC000008	reserved	2026-05-30 12:17:51.053922+00	\N	\N
9	Volkswagen	Arteon	2025	2.0T	0	45995.00	WVWSR7AN0PE000009	available	2026-06-02 12:17:51.053941+00	\N	\N
10	Volkswagen	Golf R	2025	Base	0	45640.00	1VWGF7A38PC000010	available	2026-06-05 12:17:51.053966+00	heat seat, back camera\n	on sale, come with free winter tire
\.


--
-- Data for Name: llm_request_logs; Type: TABLE DATA; Schema: public; Owner: crm_app
--

COPY public.llm_request_logs (id, url, model, input, output, created_at) FROM stdin;
1	https://www.baicai.chat/v1/chat/completions	[Azure]gpt-5.4	{"model": "[Azure]gpt-5.4", "messages": [{"role": "system", "content": "You are a writing style analyst for a car dealership sales team.\\nYour task is to study the provided sample messages and distill the writer's unique communication style\\ninto a concise, actionable markdown guide. Another AI will use this guide to write new messages\\nthat faithfully match this person's voice and style.\\n\\nThe writer's samples are organized into the following categories:\\n- Lease Expiration\\n- Test Drive Follow-Up\\n\\nProduce one ## section for each category that has samples provided, using the exact category name as the ## heading.\\nIf any sample does not match a named category, place it under ## General.\\nDo NOT produce sections for categories that have no samples.\\n\\nEach category section MUST contain exactly two sub-sections:\\n\\n### Format\\nDescribe the structural/layout conventions observed in the samples:\\n- Message length (e.g. 2-3 short paragraphs, under 80 words)\\n- Opening line pattern (greeting style, whether name is used)\\n- Body structure (e.g. one hook sentence \\u2192 offer \\u2192 CTA)\\n- Closing line pattern (sign-off, signature style)\\n- Paragraph count and spacing habits\\n- Use of bullet points, line breaks, or lists\\n\\n### Style\\nDescribe the voice and language patterns:\\n- Tone and formality level for this situation\\n- Energy level (urgent, warm, casual, professional)\\n- Vocabulary preferences and any signature phrases or pet words\\n- How they reference vehicles (make/model/year/trim usage)\\n- Use of emojis, punctuation quirks, or capitalisation habits\\n- Anything that makes this person's writing instantly recognisable\\n\\nOutput a clean markdown document. Do NOT include any samples verbatim."}, {"role": "user", "content": "Channel: email\\n\\n### Lease Expiration\\n\\nHi Andy\\nI hope this email finds you well.\\nCan you believe how quickly time flies? We want to remind you that the lease on your 2022 VW Tiguan is scheduled to mature on July 31, 2026.\\nAs you approach the end of your lease, you have a few great options available to you, and we want to make sure the transition is as smooth and seamless as possible. Whether you want to upgrade, keep your current ride, or simply hand over the keys, we are here to help you navigate the next steps.\\nYour End-of-Lease Options:\\nOption 1: Upgrade to a new model. Get behind the wheel of a brand-new vehicle with the latest technology, safety features, and a fresh warranty.\\nOption 2: Purchase your current vehicle. If you\\u2019ve fallen in love with your car and aren't ready to part ways, you can buy it out for the residual value listed in your contract.\\nOption 3: Return the vehicle. Simply schedule an inspection and return the keys to us at the end of your term.\\nLet's Find the Best Path Forward\\nWe would love to invite you back into the dealership for a quick, no-pressure chat to review these options, check out current inventory, and see what specials might apply to you.\\nPlease reply directly to this email or call us at 9024076395 to schedule a convenient time for you to drop by.\\nThank you so much for being a valued part of the O'Regan's VW family. We look forward to assisting you with your next automotive chapter!\\nWarm regards,\\nWilson Xing | Sales Consultant\\n\\n### Test Drive Follow-Up\\n\\nHi Andy,\\nThank you for taking the time to visit us yesterday and test driving the 2026 Jetta Comfortline. It was a pleasure meeting you and showing you what the Jetta has to offer.\\nI completely understand and respect your decision to test drive a few other options in the market before making your final move. Investing in a new vehicle is a big decision, and you want to ensure it\\u2019s the perfect fit.\\nWhile you are doing your research, I did want to give you a quick heads-up on an incentive that just came up for this month. Volkswagen is currently offering a 0.99% special finance rate for up to 60 months (5 years) on the 2026 Jetta. It\\u2019s one of the strongest programs we've seen in a while, and it definitely keeps the monthly payments incredibly comfortable on that Comfortline trim.\\nIf you have any questions about how those numbers look for your budget while you compare your options, just let me know.\\nI would love the opportunity to earn your business. Drive safe during your other test drives, and I look forward to connecting with you soon!\\nBest regards,\\nWilson Xing | Sales Consultant"}]}	{"choices": [{"finish_reason": "stop", "index": 0, "message": {"content": "## Lease Expiration\\n\\n### Format\\n- Medium-length email, typically around 8\\u201312 short lines/paragraph blocks.\\n- Opens with a simple greeting using the customer\\u2019s first name, usually without heavy formality.\\n- Early opening line uses a polite wellness phrase, then quickly transitions into the lease maturity reminder.\\n- Body follows a clear advisory structure:\\n  - reminder of lease end date and vehicle\\n  - reassurance that the process will be easy\\n  - presentation of available options\\n  - invitation to come in or connect\\n  - direct contact CTA\\n- Frequently uses a labeled options section with short explanatory lines for each choice.\\n- Uses multiple short paragraphs and deliberate spacing for readability.\\n- Closes with appreciation, a forward-looking sentence, then a warm professional sign-off with full name and title.\\n\\n### Style\\n- Tone is warm, supportive, and consultative rather than pushy.\\n- Professional but approachable; written to make the customer feel looked after.\\n- Uses reassuring language such as making the process \\u201csmooth,\\u201d \\u201cseamless,\\u201d and easy to navigate.\\n- Likes transitional phrases that soften sales messaging, such as acknowledging timing and presenting choices positively.\\n- Refers to vehicles with full identifying detail when relevant, typically year + brand + model.\\n- Uses upbeat, customer-care phrasing and dealership-family language to build loyalty.\\n- Calls attention to options in a structured, helpful way instead of hard-selling one path.\\n- Punctuation is standard and clean; no emojis, slang, or gimmicky formatting.\\n- Signature feel: polished dealership email voice with gratitude, clarity, and low-pressure invitation.\\n\\n## Test Drive Follow-Up\\n\\n### Format\\n- Medium-length follow-up email, usually 5\\u20137 short paragraphs.\\n- Opens with a greeting using the customer\\u2019s first name and a thank-you for visiting or test driving.\\n- First paragraph references the exact vehicle driven.\\n- Body structure is consistent:\\n  - appreciation for the visit\\n  - acknowledgment of the customer comparing other vehicles\\n  - introduction of a timely incentive or program\\n  - brief explanation of why it matters financially\\n  - invitation for questions\\n  - soft closing that asks for the opportunity to earn the business\\n- Uses paragraph breaks instead of bullets.\\n- Ends with a professional sign-off and full signature line.\\n\\n### Style\\n- Tone is respectful, patient, and sales-conscious without sounding aggressive.\\n- Strong balance of professionalism and friendliness; the writer validates the customer\\u2019s shopping process instead of resisting it.\\n- Uses empathetic language like understanding and respecting the customer\\u2019s decision-making.\\n- When presenting incentives, the writer frames them as a helpful \\u201cheads-up\\u201d rather than a pressure tactic.\\n- Financial offers are explained in practical customer terms, especially monthly payment comfort and budget fit.\\n- References vehicles with detailed naming, often year + model + trim.\\n- Uses positive, relationship-oriented lines about earning the customer\\u2019s business.\\n- Language is smooth and polished, with complete sentences and conventional punctuation.\\n- No emojis or informal shorthand; energy stays calm, warm, and confident.", "role": "assistant"}}], "created": 1781143862, "id": "chatcmpl-300d6056-5505-4de5-a356-576cb", "model": "gpt-5.4", "object": "chat.completion", "usage": {"completion_tokens": 615, "prompt_tokens": 909, "total_tokens": 1524}}	2026-06-11 02:11:04.168069+00
\.


--
-- Data for Name: outreach_rules; Type: TABLE DATA; Schema: public; Owner: crm_app
--

COPY public.outreach_rules (id, sales_id, name, rule_text, compiled_filter, cadence_days, active, created_at, email_type, custom_template) FROM stdin;
3	1	lease test rule	customer with lease and havn't contact in 30 days	{"op": "and", "conditions": [{"col": "customer_car.ownership_type", "cmp": "eq", "val": "lease"}, {"col": "customers.last_contacted_at", "cmp": "days_ago_gte", "val": 30}]}	30	t	2026-06-08 13:14:06.025746+00	test_drive_followup	\N
\.


--
-- Data for Name: sample_messages; Type: TABLE DATA; Schema: public; Owner: crm_app
--

COPY public.sample_messages (id, sales_id, channel, raw_content, label, created_at) FROM stdin;
2	1	email	Hi Andy,\nThank you for taking the time to visit us yesterday and test driving the 2026 Jetta Comfortline. It was a pleasure meeting you and showing you what the Jetta has to offer.\nI completely understand and respect your decision to test drive a few other options in the market before making your final move. Investing in a new vehicle is a big decision, and you want to ensure it’s the perfect fit.\nWhile you are doing your research, I did want to give you a quick heads-up on an incentive that just came up for this month. Volkswagen is currently offering a 0.99% special finance rate for up to 60 months (5 years) on the 2026 Jetta. It’s one of the strongest programs we've seen in a while, and it definitely keeps the monthly payments incredibly comfortable on that Comfortline trim.\nIf you have any questions about how those numbers look for your budget while you compare your options, just let me know.\nI would love the opportunity to earn your business. Drive safe during your other test drives, and I look forward to connecting with you soon!\nBest regards,\nWilson Xing | Sales Consultant	Test Drive Follow-Up	2026-06-08 13:43:09.158485+00
1	1	email	Hi Andy\nI hope this email finds you well.\nCan you believe how quickly time flies? We want to remind you that the lease on your 2022 VW Tiguan is scheduled to mature on July 31, 2026.\nAs you approach the end of your lease, you have a few great options available to you, and we want to make sure the transition is as smooth and seamless as possible. Whether you want to upgrade, keep your current ride, or simply hand over the keys, we are here to help you navigate the next steps.\nYour End-of-Lease Options:\nOption 1: Upgrade to a new model. Get behind the wheel of a brand-new vehicle with the latest technology, safety features, and a fresh warranty.\nOption 2: Purchase your current vehicle. If you’ve fallen in love with your car and aren't ready to part ways, you can buy it out for the residual value listed in your contract.\nOption 3: Return the vehicle. Simply schedule an inspection and return the keys to us at the end of your term.\nLet's Find the Best Path Forward\nWe would love to invite you back into the dealership for a quick, no-pressure chat to review these options, check out current inventory, and see what specials might apply to you.\nPlease reply directly to this email or call us at 9024076395 to schedule a convenient time for you to drop by.\nThank you so much for being a valued part of the O'Regan's VW family. We look forward to assisting you with your next automotive chapter!\nWarm regards,\nWilson Xing | Sales Consultant	Lease Expiration	2026-06-08 13:42:50.419467+00
\.


--
-- Data for Name: style_categories; Type: TABLE DATA; Schema: public; Owner: crm_app
--

COPY public.style_categories (id, sales_id, channel, name, created_at) FROM stdin;
3	1	email	Lease Expiration	2026-06-09 18:28:56.750565+00
4	1	email	Test Drive Follow-Up	2026-06-09 18:29:03.887105+00
\.


--
-- Data for Name: style_profiles; Type: TABLE DATA; Schema: public; Owner: crm_app
--

COPY public.style_profiles (id, sales_id, channel, style_md, updated_at) FROM stdin;
1	1	email	## Lease Expiration\n\n### Format\n- Medium-length email, typically around 8–12 short lines/paragraph blocks.\n- Opens with a simple greeting using the customer’s first name, usually without heavy formality.\n- Early opening line uses a polite wellness phrase, then quickly transitions into the lease maturity reminder.\n- Body follows a clear advisory structure:\n  - reminder of lease end date and vehicle\n  - reassurance that the process will be easy\n  - presentation of available options\n  - invitation to come in or connect\n  - direct contact CTA\n- Frequently uses a labeled options section with short explanatory lines for each choice.\n- Uses multiple short paragraphs and deliberate spacing for readability.\n- Closes with appreciation, a forward-looking sentence, then a warm professional sign-off with full name and title.\n\n### Style\n- Tone is warm, supportive, and consultative rather than pushy.\n- Professional but approachable; written to make the customer feel looked after.\n- Uses reassuring language such as making the process “smooth,” “seamless,” and easy to navigate.\n- Likes transitional phrases that soften sales messaging, such as acknowledging timing and presenting choices positively.\n- Refers to vehicles with full identifying detail when relevant, typically year + brand + model.\n- Uses upbeat, customer-care phrasing and dealership-family language to build loyalty.\n- Calls attention to options in a structured, helpful way instead of hard-selling one path.\n- Punctuation is standard and clean; no emojis, slang, or gimmicky formatting.\n- Signature feel: polished dealership email voice with gratitude, clarity, and low-pressure invitation.\n\n## Test Drive Follow-Up\n\n### Format\n- Medium-length follow-up email, usually 5–7 short paragraphs.\n- Opens with a greeting using the customer’s first name and a thank-you for visiting or test driving.\n- First paragraph references the exact vehicle driven.\n- Body structure is consistent:\n  - appreciation for the visit\n  - acknowledgment of the customer comparing other vehicles\n  - introduction of a timely incentive or program\n  - brief explanation of why it matters financially\n  - invitation for questions\n  - soft closing that asks for the opportunity to earn the business\n- Uses paragraph breaks instead of bullets.\n- Ends with a professional sign-off and full signature line.\n\n### Style\n- Tone is respectful, patient, and sales-conscious without sounding aggressive.\n- Strong balance of professionalism and friendliness; the writer validates the customer’s shopping process instead of resisting it.\n- Uses empathetic language like understanding and respecting the customer’s decision-making.\n- When presenting incentives, the writer frames them as a helpful “heads-up” rather than a pressure tactic.\n- Financial offers are explained in practical customer terms, especially monthly payment comfort and budget fit.\n- References vehicles with detailed naming, often year + model + trim.\n- Uses positive, relationship-oriented lines about earning the customer’s business.\n- Language is smooth and polished, with complete sentences and conventional punctuation.\n- No emojis or informal shorthand; energy stays calm, warm, and confident.	2026-06-11 02:10:41.89309+00
\.


--
-- Data for Name: user_settings; Type: TABLE DATA; Schema: public; Owner: crm_app
--

COPY public.user_settings (user_id, key, value, updated_at) FROM stdin;
1	llm_base_url	https://www.baicai.chat/v1	2026-06-10 19:39:14.174467+00
1	llm_api_key	sk-COoVPNSsE1WxE98y4NC2AYWbUgGXm12VJyyJnLP5ruBTphRM	2026-06-10 19:39:14.174467+00
1	llm_model	[Azure]gpt-5.4	2026-06-10 19:39:14.174467+00
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: crm_app
--

COPY public.users (id, email, password_hash, name, role, must_change_password, created_at) FROM stdin;
1	admin@dealer.local	$argon2id$v=19$m=65536,t=3,p=4$ib8noLpcfpSXsrMhiJ001Q$8e1B0Lpeadw5DWrTOCBZTYvhlNyOLt2yWcI3zPTwXgg	Admin	manager	f	2026-06-06 23:13:49.956893+00
\.


--
-- Name: customer_car_id_seq; Type: SEQUENCE SET; Schema: public; Owner: crm_app
--

SELECT pg_catalog.setval('public.customer_car_id_seq', 9, true);


--
-- Name: customers_id_seq; Type: SEQUENCE SET; Schema: public; Owner: crm_app
--

SELECT pg_catalog.setval('public.customers_id_seq', 11, true);


--
-- Name: email_drafts_id_seq; Type: SEQUENCE SET; Schema: public; Owner: crm_app
--

SELECT pg_catalog.setval('public.email_drafts_id_seq', 8, true);


--
-- Name: interactions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: crm_app
--

SELECT pg_catalog.setval('public.interactions_id_seq', 14, true);


--
-- Name: inventory_id_seq; Type: SEQUENCE SET; Schema: public; Owner: crm_app
--

SELECT pg_catalog.setval('public.inventory_id_seq', 10, true);


--
-- Name: llm_request_logs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: crm_app
--

SELECT pg_catalog.setval('public.llm_request_logs_id_seq', 1, true);


--
-- Name: outreach_rules_id_seq; Type: SEQUENCE SET; Schema: public; Owner: crm_app
--

SELECT pg_catalog.setval('public.outreach_rules_id_seq', 3, true);


--
-- Name: sample_messages_id_seq; Type: SEQUENCE SET; Schema: public; Owner: crm_app
--

SELECT pg_catalog.setval('public.sample_messages_id_seq', 2, true);


--
-- Name: style_categories_id_seq; Type: SEQUENCE SET; Schema: public; Owner: crm_app
--

SELECT pg_catalog.setval('public.style_categories_id_seq', 4, true);


--
-- Name: style_profiles_id_seq; Type: SEQUENCE SET; Schema: public; Owner: crm_app
--

SELECT pg_catalog.setval('public.style_profiles_id_seq', 1, true);


--
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: crm_app
--

SELECT pg_catalog.setval('public.users_id_seq', 1, true);


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: app_settings app_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.app_settings
    ADD CONSTRAINT app_settings_pkey PRIMARY KEY (key);


--
-- Name: customer_car customer_car_pkey; Type: CONSTRAINT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.customer_car
    ADD CONSTRAINT customer_car_pkey PRIMARY KEY (id);


--
-- Name: customers customers_pkey; Type: CONSTRAINT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.customers
    ADD CONSTRAINT customers_pkey PRIMARY KEY (id);


--
-- Name: email_drafts email_drafts_pkey; Type: CONSTRAINT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.email_drafts
    ADD CONSTRAINT email_drafts_pkey PRIMARY KEY (id);


--
-- Name: interactions interactions_pkey; Type: CONSTRAINT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.interactions
    ADD CONSTRAINT interactions_pkey PRIMARY KEY (id);


--
-- Name: inventory inventory_pkey; Type: CONSTRAINT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.inventory
    ADD CONSTRAINT inventory_pkey PRIMARY KEY (id);


--
-- Name: inventory inventory_vin_key; Type: CONSTRAINT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.inventory
    ADD CONSTRAINT inventory_vin_key UNIQUE (vin);


--
-- Name: llm_request_logs llm_request_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.llm_request_logs
    ADD CONSTRAINT llm_request_logs_pkey PRIMARY KEY (id);


--
-- Name: outreach_rules outreach_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.outreach_rules
    ADD CONSTRAINT outreach_rules_pkey PRIMARY KEY (id);


--
-- Name: sample_messages sample_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.sample_messages
    ADD CONSTRAINT sample_messages_pkey PRIMARY KEY (id);


--
-- Name: style_categories style_categories_pkey; Type: CONSTRAINT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.style_categories
    ADD CONSTRAINT style_categories_pkey PRIMARY KEY (id);


--
-- Name: style_profiles style_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.style_profiles
    ADD CONSTRAINT style_profiles_pkey PRIMARY KEY (id);


--
-- Name: style_categories uq_style_category; Type: CONSTRAINT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.style_categories
    ADD CONSTRAINT uq_style_category UNIQUE (sales_id, channel, name);


--
-- Name: style_profiles uq_style_sales_channel; Type: CONSTRAINT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.style_profiles
    ADD CONSTRAINT uq_style_sales_channel UNIQUE (sales_id, channel);


--
-- Name: user_settings user_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.user_settings
    ADD CONSTRAINT user_settings_pkey PRIMARY KEY (user_id, key);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: ix_customer_car_customer_id; Type: INDEX; Schema: public; Owner: crm_app
--

CREATE INDEX ix_customer_car_customer_id ON public.customer_car USING btree (customer_id);


--
-- Name: ix_customers_assigned_sales_id; Type: INDEX; Schema: public; Owner: crm_app
--

CREATE INDEX ix_customers_assigned_sales_id ON public.customers USING btree (assigned_sales_id);


--
-- Name: ix_email_drafts_customer_id; Type: INDEX; Schema: public; Owner: crm_app
--

CREATE INDEX ix_email_drafts_customer_id ON public.email_drafts USING btree (customer_id);


--
-- Name: ix_email_drafts_sales_id; Type: INDEX; Schema: public; Owner: crm_app
--

CREATE INDEX ix_email_drafts_sales_id ON public.email_drafts USING btree (sales_id);


--
-- Name: ix_interactions_customer_id; Type: INDEX; Schema: public; Owner: crm_app
--

CREATE INDEX ix_interactions_customer_id ON public.interactions USING btree (customer_id);


--
-- Name: ix_interactions_sales_id; Type: INDEX; Schema: public; Owner: crm_app
--

CREATE INDEX ix_interactions_sales_id ON public.interactions USING btree (sales_id);


--
-- Name: ix_outreach_rules_sales_id; Type: INDEX; Schema: public; Owner: crm_app
--

CREATE INDEX ix_outreach_rules_sales_id ON public.outreach_rules USING btree (sales_id);


--
-- Name: ix_sample_messages_sales_id; Type: INDEX; Schema: public; Owner: crm_app
--

CREATE INDEX ix_sample_messages_sales_id ON public.sample_messages USING btree (sales_id);


--
-- Name: ix_style_categories_sales_id; Type: INDEX; Schema: public; Owner: crm_app
--

CREATE INDEX ix_style_categories_sales_id ON public.style_categories USING btree (sales_id);


--
-- Name: customer_car customer_car_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.customer_car
    ADD CONSTRAINT customer_car_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(id) ON DELETE CASCADE;


--
-- Name: customers customers_assigned_sales_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.customers
    ADD CONSTRAINT customers_assigned_sales_id_fkey FOREIGN KEY (assigned_sales_id) REFERENCES public.users(id);


--
-- Name: email_drafts email_drafts_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.email_drafts
    ADD CONSTRAINT email_drafts_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(id) ON DELETE CASCADE;


--
-- Name: email_drafts email_drafts_rule_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.email_drafts
    ADD CONSTRAINT email_drafts_rule_id_fkey FOREIGN KEY (rule_id) REFERENCES public.outreach_rules(id) ON DELETE SET NULL;


--
-- Name: email_drafts email_drafts_sales_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.email_drafts
    ADD CONSTRAINT email_drafts_sales_id_fkey FOREIGN KEY (sales_id) REFERENCES public.users(id);


--
-- Name: interactions interactions_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.interactions
    ADD CONSTRAINT interactions_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.customers(id) ON DELETE CASCADE;


--
-- Name: interactions interactions_sales_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.interactions
    ADD CONSTRAINT interactions_sales_id_fkey FOREIGN KEY (sales_id) REFERENCES public.users(id);


--
-- Name: outreach_rules outreach_rules_sales_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.outreach_rules
    ADD CONSTRAINT outreach_rules_sales_id_fkey FOREIGN KEY (sales_id) REFERENCES public.users(id);


--
-- Name: sample_messages sample_messages_sales_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.sample_messages
    ADD CONSTRAINT sample_messages_sales_id_fkey FOREIGN KEY (sales_id) REFERENCES public.users(id);


--
-- Name: style_categories style_categories_sales_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.style_categories
    ADD CONSTRAINT style_categories_sales_id_fkey FOREIGN KEY (sales_id) REFERENCES public.users(id);


--
-- Name: style_profiles style_profiles_sales_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.style_profiles
    ADD CONSTRAINT style_profiles_sales_id_fkey FOREIGN KEY (sales_id) REFERENCES public.users(id);


--
-- Name: user_settings user_settings_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: crm_app
--

ALTER TABLE ONLY public.user_settings
    ADD CONSTRAINT user_settings_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict VEbWeIkXQ1quNmGLK6VjOw1U6UDF76t4YDCxIgCZ9Wa5VBKqnbp1JuaCFDiSpQg


